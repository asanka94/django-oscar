from django.conf import settings
from django.core.management.base import BaseCommand

from django_elasticsearch_dsl.registries import registry

from .base import UpdateDocumentsMixin
from ...registries import AnalyzerRegistry


class Command(UpdateDocumentsMixin, BaseCommand):
    help = "Completely rebuilds the search index by removing the old data and then updating."

    def rebuild_index(self, index):
        index.delete(ignore=404)

        self.stdout.write("Creating index '{}'".format(index))

        analyzer_registry = AnalyzerRegistry()
        analyzer_registry.define_in_index(index)

        index.settings(**settings.OSCAR_SEARCH['INDEX_CONFIG'])
        index.create()

    def handle(self, **options):
        for index in registry.get_indices():
            self.rebuild_index(index)

        self.update_documents()
