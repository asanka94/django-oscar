from django_elasticsearch_dsl.registries import registry


class UpdateDocumentsMixin(object):

    def update_documents(self):
        for Document in registry.get_documents():
            doc = Document()
            qs = doc.get_queryset()
            self.stdout.write("Indexing {} '{}' objects".format(
                qs.count(), doc._doc_type.model.__name__)
            )
            doc.update(qs.iterator())
