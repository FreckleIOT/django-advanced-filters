import sys

from django.test import TestCase
try:
    from django.test import override_settings
except ImportError:
    from django.test.utils import override_settings
from django.utils.encoding import force_text
try:
    from django.urls import reverse
except ImportError:  # Django < 2.0
    from django.core.urlresolvers import reverse
import django

from tests import factories


class TestGetFieldChoicesView(TestCase):
    url_name = 'afilters_get_field_choices'

    def setUp(self):
        self.user = factories.SalesRep()
        assert self.client.login(username='user', password='test')

    def assert_json(self, response, expect):
        self.assertJSONEqual(force_text(response.content), expect)

    def assert_view_error(self, error, exception=None, **view_kwargs):
        """ Ensure view either raises exception or returns a 400 json error """
        view_url = reverse(self.url_name, kwargs=view_kwargs)
        if exception is not None:
            self.assertRaisesMessage(
                exception, error, self.client.get, view_url)
            return
        res = self.client.get(view_url)
        assert res.status_code == 400
        self.assert_json(res, dict(error=error))

    def test_invalid_args(self):
        self.assert_view_error("GetFieldChoices view requires 2 arguments")
        if 'PyPy' in getattr(sys, 'subversion', ()):
            self.assert_view_error(
                'expected length 2, got 1',
                model='a', field_name='b', exception=ValueError)
        elif sys.version_info >= (3, 5):
            self.assert_view_error(
                'not enough values to unpack (expected 2, got 1)', model='a',
                field_name='b', exception=ValueError)
        else:
            self.assert_view_error(
                'need more than 1 value to unpack', model='a',
                field_name='b', exception=ValueError)
        if django.VERSION >= (1, 11):
            self.assert_view_error("No installed app with label 'Foo'.",
                                   model='Foo.test', field_name='baz')
            self.assert_view_error("App 'reps' doesn't have a 'Foo' model.",
                                   model='reps.Foo', field_name='b')
        elif django.VERSION >= (1, 7):
            self.assert_view_error("No installed app with label 'foo'.",
                                   model='foo.test', field_name='baz')
            self.assert_view_error("App 'reps' doesn't have a 'foo' model.",
                                   model='reps.Foo', field_name='b')
        else:
            self.assert_view_error("No installed app/model: foo.test",
                                   model='foo.test', field_name='baz')
            self.assert_view_error("No installed app/model: reps.Foo",
                                   model='reps.Foo', field_name='b')
        if sys.version_info >= (3, 3) or django.VERSION >= (1, 11):
            expected_exception = "SalesRep has no field named 'baz'"
        else:
            expected_exception = "SalesRep has no field named u'baz'"
        self.assert_view_error(expected_exception,
                               model='reps.SalesRep', field_name='baz')


    def test_field_with_choices(self):
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='language'))
        res = self.client.get(view_url)
        self.assert_json(res, {
            'results': [
                {'id': 'en', 'text': 'English'},
                {'id': 'it', 'text': 'Italian'},
                {'id': 'sp', 'text': 'Spanish'}
            ],
            'more': False,
        })

    @override_settings(ADVANCED_FILTERS_DISABLE_FOR_FIELDS=('email',))
    def test_disabled_field(self):
        factories.Client.create_batch(3, assigned_to=self.user)
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='email'))
        res = self.client.get(view_url)
        self.assert_json(res, {'results': [], 'more': False})

    def test_disabled_field_types(self):
        factories.Client.create_batch(3, assigned_to=self.user)
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='is_active'))
        res = self.client.get(view_url)
        self.assert_json(res, {'results': [], 'more': False})

    def test_database_choices(self):
        clients = factories.Client.create_batch(3, assigned_to=self.user)
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='email'))
        res = self.client.get(view_url)
        self.assert_json(res, {
            'results': [dict(id=e.email, text=e.email) for e in clients],
            'more': False
        })

    def test_distinct_database_choices(self):
        factories.Client.create_batch(5, assigned_to=self.user, email="foo@bar.com")
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='email'))
        res = self.client.get(view_url)
        self.assert_json(res, {'results': [{'id': 'foo@bar.com', 'text': 'foo@bar.com'}], 'more': False})

    def test_search(self):
        factories.Client.create(assigned_to=self.user, first_name="Franscisco")
        factories.Client.create(assigned_to=self.user, first_name="Cindy")
        factories.Client.create(assigned_to=self.user, first_name="John")
        factories.Client.create(assigned_to=self.user, first_name="Mark")
        factories.Client.create(assigned_to=self.user, first_name="Patricia")
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='first_name'))
        res = self.client.get(view_url, {'search': 'ci'})
        self.assert_json(res, {
            'results': [
                {'id': 'Cindy', 'text': 'Cindy'},
                {'id': 'Franscisco', 'text': 'Franscisco'},
                {'id': 'Patricia', 'text': 'Patricia'},
            ],
            'more': False
        })

    @override_settings(ADVANCED_FILTERS_PAGE_SIZE=3)
    def test_multiple_pages(self):
        factories.Client.create(assigned_to=self.user, first_name="Franscisco")
        factories.Client.create(assigned_to=self.user, first_name="Cindy")
        factories.Client.create(assigned_to=self.user, first_name="John")
        factories.Client.create(assigned_to=self.user, first_name="Mark")
        factories.Client.create(assigned_to=self.user, first_name="Paul")
        factories.Client.create(assigned_to=self.user, first_name="Amelie")
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='first_name'))
        res = self.client.get(view_url, {'page': '1'})
        self.assert_json(res, {
            'results': [
                {'id': 'Amelie', 'text': 'Amelie'},
                {'id': 'Cindy', 'text': 'Cindy'},
                {'id': 'Franscisco', 'text': 'Franscisco'},
            ],
            'more': True
        })
        res = self.client.get(view_url, {'page': '2'})
        self.assert_json(res, {
            'results': [
                {'id': 'John', 'text': 'John'},
                {'id': 'Mark', 'text': 'Mark'},
                {'id': 'Paul', 'text': 'Paul'},
            ],
            'more': False
        })

    @override_settings(ADVANCED_FILTERS_PAGE_SIZE=3)
    def test_invalid_page(self):
        factories.Client.create(assigned_to=self.user, first_name="Mark")
        factories.Client.create(assigned_to=self.user, first_name="Paul")
        factories.Client.create(assigned_to=self.user, first_name="Amelie")
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='first_name'))
        res = self.client.get(view_url, {'page': '2'})
        self.assert_json(res, {
            'results': [],
            'more': False
        })


class TestGetOperatorChoices(TestCase):
    url_name = 'afilters_get_operator_choices'

    def setUp(self):
        self.user = factories.SalesRep()
        assert self.client.login(username='user', password='test')

    def assert_json(self, response, expect):
        self.assertJSONEqual(force_text(response.content), expect)

    def assert_view_error(self, error, exception=None, **view_kwargs):
        """ Ensure view either raises exception or returns a 400 json error """
        view_url = reverse(self.url_name, kwargs=view_kwargs)
        if exception is not None:
            self.assertRaisesMessage(
                exception, error, self.client.get, view_url)
            return
        res = self.client.get(view_url)
        assert res.status_code == 400
        self.assert_json(res, dict(error=error))

    def test_invalid_args(self):
        self.assert_view_error("GetOperatorChoices view requires 2 arguments")
        if 'PyPy' in getattr(sys, 'subversion', ()):
            self.assert_view_error(
                'expected length 2, got 1',
                model='a', field_name='b', exception=ValueError)
        elif sys.version_info >= (3, 5):
            self.assert_view_error(
                'not enough values to unpack (expected 2, got 1)', model='a',
                field_name='b', exception=ValueError)
        else:
            self.assert_view_error(
                'need more than 1 value to unpack', model='a',
                field_name='b', exception=ValueError)
        if django.VERSION >= (1, 11):
            self.assert_view_error("No installed app with label 'Foo'.",
                                   model='Foo.test', field_name='baz')
            self.assert_view_error("App 'reps' doesn't have a 'Foo' model.",
                                   model='reps.Foo', field_name='b')
        elif django.VERSION >= (1, 7):
            self.assert_view_error("No installed app with label 'foo'.",
                                   model='foo.test', field_name='baz')
            self.assert_view_error("App 'reps' doesn't have a 'foo' model.",
                                   model='reps.Foo', field_name='b')
        else:
            self.assert_view_error("No installed app/model: foo.test",
                                   model='foo.test', field_name='baz')
            self.assert_view_error("No installed app/model: reps.Foo",
                                   model='reps.Foo', field_name='b')
        if sys.version_info >= (3, 3) or django.VERSION >= (1, 11):
            expected_exception = "SalesRep has no field named 'baz'"
        else:
            expected_exception = "SalesRep has no field named u'baz'"
        self.assert_view_error(expected_exception,
                               model='reps.SalesRep', field_name='baz')

    def test_field_with_choices(self):
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='language'))
        res = self.client.get(view_url)
        self.assert_json(res, {
            'results': ['isnull', 'iexact', 'icontains', 'iregex']
        })

    @override_settings(ADVANCED_FILTERS_DISABLE_FOR_FIELDS=('email',))
    def test_disabled_field(self):
        factories.Client.create_batch(3, assigned_to=self.user)
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='email'))
        res = self.client.get(view_url)
        self.assert_json(res, {'results': []})

    def test_boolean_field(self):
        factories.Client.create_batch(3, assigned_to=self.user)
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='is_active'))
        res = self.client.get(view_url)
        self.assert_json(res, {'results': ['isnull', 'istrue', 'isfalse']})

    def test_database_choices(self):
        factories.Client.create_batch(3, assigned_to=self.user)
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='email'))
        res = self.client.get(view_url)
        self.assert_json(res, {
            'results': ['isnull', 'iexact', 'icontains', 'iregex']
            })

    def test_datetime_field(self):
        factories.Client.create_batch(3, assigned_to=self.user)
        view_url = reverse(self.url_name, kwargs=dict(
            model='customers.Client', field_name='date_joined'))
        res = self.client.get(view_url)
        self.assert_json(res, {
            'results': ["isnull", "range", "lt", "gt", "lte", "gte"]
            })
