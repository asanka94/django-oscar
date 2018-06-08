from django.core.management.base import BaseCommand

from .base import UpdateDocumentsMixin


class Command(UpdateDocumentsMixin, BaseCommand):
    help = "Completely rebuilds the search index by removing the old data and then updating."

    def handle(self, **options):
        self.update_documents()
