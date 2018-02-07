from dateutil.relativedelta import relativedelta

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import ProgrammingError
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.six import with_metaclass

from oscar.apps.catalogue.models import AttributeOption
from oscar.core.loading import get_model

from django_elasticsearch_dsl.documents import DocTypeMeta
from django_elasticsearch_dsl import DocType, fields
from elasticsearch_dsl import Mapping, MetaField


Line = get_model('order', 'Line')
Product = get_model('catalogue', 'Product')
ProductAttribute = get_model('catalogue', 'ProductAttribute')

product_mapping = Mapping('product')
product_mapping.field('raw_title', 'text', boost=1.25)
product_mapping.field('all_skus', 'text', analyzer='standard')


ATTRIBUTE_TYPE_ES_FIELDS = {
    ProductAttribute.TEXT: fields.KeywordField,
    ProductAttribute.INTEGER: fields.IntegerField,
    ProductAttribute.BOOLEAN: fields.BooleanField,
    ProductAttribute.FLOAT: fields.FloatField,
    ProductAttribute.RICHTEXT: fields.KeywordField,
    ProductAttribute.DATE: fields.DateField,
    ProductAttribute.DATETIME: fields.DateField,
    ProductAttribute.OPTION: fields.KeywordField,
    ProductAttribute.MULTI_OPTION: fields.KeywordField
}


class ProductDocumentMeta(DocTypeMeta):

    def __new__(cls, name, bases, attrs):
        attrs['product_attributes'] = []

        try:
            indexed_attributes = ProductAttribute.objects.filter(code__in=getattr(settings, 'OSCAR_SEARCH_FACETS', {}).keys())
            for attr in indexed_attributes:
                # don't add it if a custom field is already defined
                if attr.code not in attrs:
                    attrs[attr.code] = ATTRIBUTE_TYPE_ES_FIELDS[attr.type](index='not_analyzed', include_in_all=False)

                attrs['product_attributes'].append(attr.code)

        # without this we can't run migrations on a new database
        except ProgrammingError:
            pass

        attr_copy = attrs.copy()
        cls = super(ProductDocumentMeta, cls).__new__(cls, name, bases, attrs)
        for attr in attrs['product_attributes']:
            setattr(cls, attr, attr_copy[attr])

        return cls


class ProductDocument(with_metaclass(ProductDocumentMeta, DocType)):

    upc = fields.TextField(
        analyzer="edgengram_analyzer",
        search_analyzer="standard"
    )
    title = fields.TextField(
        analyzer="ngram_analyzer",
        search_analyzer="standard",
        copy_to="raw_title"
    )
    description = fields.TextField(
        analyzer="english"
    )
    stock = fields.ListField(field=fields.NestedField(properties={
        'currency': fields.KeywordField(index='not_analyzed'),
        'sku': fields.KeywordField(copy_to='all_skus'),
        'price': fields.FloatField(),
        'partner': fields.IntegerField(index='not_analyzed'),
        'num_in_stock': fields.IntegerField(index='not_analyzed')
    }, include_in_all=False))
    categories = fields.ListField(field=fields.IntegerField(
        include_in_all=False
    ))
    score = fields.FloatField(include_in_all=False)
    url = fields.TextField(
        index=False,
        attr="get_absolute_url"
    )

    def __getattr__(self, name):
        # return a function that will be used to fetch product attribute values from the product

        # e.g prepare_price will fetch product.attr.price if price is in self.product_attributes
        if name.startswith('prepare_'):
            attribute_name = name.split('prepare_', 1)[1]
            if attribute_name in self.product_attributes:
                return lambda product: self.prepare_attribute(product, attribute_name)

        return super(ProductDocument, self).__getattr__(name)

    def prepare_attribute(self, product, attribute_name):
        attr = getattr(product.attr, attribute_name, None)
        if isinstance(attr, QuerySet):
            # Multi option, get the list of values directly from database.
            return list(attr.values_list('multi_valued_attribute_values__value_multi_option__option', flat=True).distinct())
        elif isinstance(attr, AttributeOption):
            return attr.option
        else:
            return attr

    def prepare(self, instance):
        data = super(ProductDocument, self).prepare(instance)

        # remove attribute data for attributes that don't exist for this product
        final_data = data.copy()
        for key in data:
            if key in self.product_attributes:
                try:
                    getattr(instance.attr, key)
                except AttributeError:
                    del final_data[key]

        return final_data

    @staticmethod
    def sanitize_description(description):
        return ' '.join(strip_tags(description).strip().split())

    def prepare_description(self, product):
        return self.sanitize_description(product.description)

    def prepare_stock(self, product):
        if product.is_parent or not product.has_stockrecords:
            # For parent products... we don't currently handle this case
            return None

        stocks = []
        for stockrecord in product.stockrecords.all():
            stocks.append(self.get_stockrecord_data(stockrecord))

        return stocks

    def prepare_categories(self, product):
        categories = product.categories.all()
        all_cats = set()
        for cat in categories:
            all_cats.add(cat.pk)
            all_cats.update(set(cat.get_ancestors().values_list('id', flat=True)))
        return list(all_cats)

    def prepare_score(self, product):
        months_to_run = getattr(settings, 'MONTHS_TO_RUN_ANALYTICS', 3)
        orders_above_date = timezone.now() - relativedelta(months=months_to_run)

        return Line.objects.filter(product=product, order__date_placed__gte=orders_above_date).count()

    def prepare_manufacturer(self, product):
        return product.manufacturer.name if product.manufacturer else None

    def get_stockrecord_data(self, stockrecord):
        # Exclude stock records that have no price
        if not stockrecord.price_excl_tax:
            return None

        # Partner can be missing when loading data from fixtures
        try:
            partner = stockrecord.partner.pk
        except ObjectDoesNotExist:
            return None

        return {
            'partner': partner,
            'currency': stockrecord.price_currency,
            'price': stockrecord.price_excl_tax,
            'num_in_stock': stockrecord.net_stock_level,
            'sku': stockrecord.partner_sku
        }

    class Meta:
        doc_type = 'product'
        index = settings.ELASTICSEARCH_INDEX_NAME
        model = Product
        mapping = product_mapping
        dynamic = MetaField('strict')
