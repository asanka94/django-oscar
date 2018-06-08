from unittest import mock

from django.test import TestCase, override_settings
from django_elasticsearch_dsl import Index

from oscar.apps.es_search.registries import AnalyzerRegistry

from tests._site.search_tests_app.analyzers import test_analyzer


class AnalyzerRegistryTestCase(TestCase):

    @override_settings(OSCAR_SEARCH={'ANALYZERS': [
        'tests._site.search_tests_app.analyzers.test_analyzer',
        'tests._site.search_tests_app.analyzers.test_analyzer_2'
    ]})
    def test_raises_error_if_trying_to_register_analyzer_with_registered_name(self):
        analyzer_registry = AnalyzerRegistry()
        index = Index('test')
        with self.assertRaises(KeyError):
            analyzer_registry.define_in_index(index)

    @override_settings(OSCAR_SEARCH={'ANALYZERS': ['tests._site.search_tests_app.analyzers.test_analyzer']})
    def test_define_in_index_finds_analyzers_in_analyzer_dot_py_files(self):
        with mock.patch.object(Index, 'analyzer') as mock_analyzer:
            index = Index('test')

            analyzer_registry = AnalyzerRegistry()
            analyzer_registry.define_in_index(index)

            mock_analyzer.assert_called_with(test_analyzer)

    @override_settings(OSCAR_SEARCH={'ANALYZERS': [
        'tests._site.search_tests_app.analyzers.test_analyzer_that_doesnt_exist'
    ]})
    def test_raises_import_error_if_defined_analyzer_doesnt_exist(self):
        with self.assertRaises(ImportError):
            AnalyzerRegistry().define_in_index(Index('test'))
