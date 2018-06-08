from django.conf import settings
from django.db import models
from django.test import TestCase
from django_elasticsearch_dsl import DocType

from unittest.mock import MagicMock, patch, call

from oscar.apps.es_search.management.commands.base import UpdateDocumentsMixin
from oscar.apps.es_search.management.commands.rebuild_oscar_index import Command as RebuildOscarIndexCommand
from oscar.apps.es_search.management.commands.update_oscar_index import Command as UpdateOscarIndexCommand


class UpdateDocumentsMixinTestCase(TestCase):

    def test_update_documents_calls_Document_update_on_the_Documents_queryset(self):
        class Model(models.Model):
            class Meta:
                app_label = 'model'

        class Doc(DocType):
            class Meta:
                model = Model

        qs = MagicMock()
        Doc.get_queryset = MagicMock(return_value=qs)
        Doc.update = MagicMock()

        with patch('oscar.apps.es_search.management.commands.base.registry.get_documents', return_value=[Doc]):
            updater = UpdateDocumentsMixin()
            updater.stdout = MagicMock()
            updater.update_documents()

            Doc.update.assert_called_with(qs.iterator())


class RebuildOscarIndexTestCase(TestCase):

    def test_command_deletes_existing_indices(self):
        index = MagicMock()
        cmd = RebuildOscarIndexCommand()
        cmd.rebuild_index(index)

        index.delete.assert_called_with(ignore=404)

    @patch('oscar.apps.es_search.management.commands.rebuild_oscar_index.AnalyzerRegistry.define_in_index')
    def test_analyzers_defined_for_indices(self, define_in_index_mock):
        index = MagicMock()

        cmd = RebuildOscarIndexCommand()
        cmd.rebuild_index(index)

        define_in_index_mock.assert_called_with(index)

    def test_index_settings_set_from_OSCAR_SEARCH_INDEX_CONFIG(self):
        index = MagicMock()
        cmd = RebuildOscarIndexCommand()
        cmd.rebuild_index(index)

        index.settings.assert_called_with(**settings.OSCAR_SEARCH['INDEX_CONFIG'])

    def test_index_create_called_in_rebuild_command(self):
        index = MagicMock()
        cmd = RebuildOscarIndexCommand()
        cmd.rebuild_index(index)

        self.assertTrue(index.create.called)

    def test_rebuild_index_and_update_documents_are_called_rebuild_command(self):
        index1 = MagicMock()
        index2 = MagicMock()
        indices = [index1, index2]

        with patch('oscar.apps.es_search.management.commands.rebuild_oscar_index.registry.get_indices',
                   return_value=indices):
            with patch.object(RebuildOscarIndexCommand, 'rebuild_index') as rebuild_index_mock:
                with patch.object(RebuildOscarIndexCommand, 'update_documents') as update_docs_mock:
                    cmd = RebuildOscarIndexCommand()
                    cmd.handle()

                    self.assertTrue(update_docs_mock.called)

                    rebuild_index_mock.assert_has_calls([call(index1), call(index2)])


class UpdateOscarIndexTestCase(TestCase):

    def test_update_documents_called_in_update_command(self):
        with patch.object(UpdateOscarIndexCommand, 'update_documents') as update_docs_mock:
            cmd = UpdateOscarIndexCommand()
            cmd.handle()

            self.assertTrue(update_docs_mock.called)
