from django.conf import settings
from django_elasticsearch_dsl import DocType, fields as dsl_fields

from .models import SearchModel


class SearchDocument(DocType):

    title = dsl_fields.TextField()

    class Meta:
        doc_type = 'test'
        model = SearchModel
        index = settings.OSCAR_SEARCH['INDEX_NAME']
