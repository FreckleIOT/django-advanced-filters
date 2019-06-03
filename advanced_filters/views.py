from operator import itemgetter
import logging

from django.apps import apps
from django.conf import settings
from django.contrib.admin.utils import get_fields_from_path
from django.db import models
from django.db.models.fields import FieldDoesNotExist
from django.utils.encoding import force_text
from django.views.generic import View

from braces.views import (CsrfExemptMixin, StaffuserRequiredMixin,
                          JSONResponseMixin)
from advanced_filters.forms import AdvancedFilterQueryForm

from django.core.paginator import Paginator, EmptyPage

logger = logging.getLogger('advanced_filters.views')


class GetFieldChoices(CsrfExemptMixin, StaffuserRequiredMixin,
                      JSONResponseMixin, View):
    """
    A JSONResponse view that accepts a model and a field (path to field),
    resolves and returns the valid choices for that field.
    Model must use the "app.Model" notation.

    If this field is not a simple Integer/CharField with predefined choices,
    all distinct entries in the DB are presented, unless field name is in
    ADVANCED_FILTERS_DISABLE_FOR_FIELDS and limited to display only results
    under ADVANCED_FILTERS_MAX_CHOICES.
    """
    def get(self, request, model=None, field_name=None):
        search = request.GET.get('search', '')
        page = request.GET.get('page', 1)
        has_next = False
        if model is field_name is None:
            return self.render_json_response(
                {'error': "GetFieldChoices view requires 2 arguments"},
                status=400)
        app_label, model_name = model.split('.', 1)
        try:
            model_obj = apps.get_model(app_label, model_name)
            field = get_fields_from_path(model_obj, field_name)[-1]
            model_obj = field.model  # use new model if followed a ForeignKey
        except AttributeError as e:
            logger.debug("Invalid kwargs passed to view: %s", e)
            return self.render_json_response(
                {'error': "No installed app/model: %s" % model}, status=400)
        except (LookupError, FieldDoesNotExist) as e:
            logger.debug("Invalid kwargs passed to view: %s", e)
            return self.render_json_response(
                {'error': force_text(e)}, status=400)

        choices = field.choices
        choices = sorted(choices)
        # if no choices, populate with distinct values from instances
        if not choices:
            choices = []
            disabled = getattr(settings, 'ADVANCED_FILTERS_DISABLE_FOR_FIELDS',
                               tuple())
            if field.name in disabled:
                logger.debug('Skipped lookup of choices for disabled fields')
            elif isinstance(field, (models.BooleanField, models.DateField,
                                    models.TimeField)):
                logger.debug('No choices calculated for field %s of type %s',
                             field, type(field))
            else:
                # the order_by() avoids ambiguity with values() and distinct()
                filter_kwargs = {
                    "{}__icontains".format(field.name): search,
                    "{}__isnull".format(field.name): False
                }
                queryset = model_obj.objects.filter(
                    **filter_kwargs).order_by(field.name).values_list(
                        field.name, flat=True).distinct()
                page_size = getattr(
                    settings, 'ADVANCED_FILTERS_PAGE_SIZE', 20)
                paginator = Paginator(queryset, page_size)
                try:
                    page = paginator.page(page)
                    choices = zip(page, page)
                    has_next = page.has_next()
                except EmptyPage:
                    choices = []
                    has_next = False

        results = [{'id': c[0], 'text': force_text(c[1])} for c in choices]

        return self.render_json_response(
            {'results': results, "more": has_next})


class GetOperatorChoices(CsrfExemptMixin, StaffuserRequiredMixin,
                         JSONResponseMixin, View):

    def get(self, request, model=None, field_name=None):
        if model is field_name is None:
            return self.render_json_response(
                {'error': "GetOperatorChoices view requires 2 arguments"},
                status=400)
        app_label, model_name = model.split('.', 1)
        try:
            model_obj = apps.get_model(app_label, model_name)
            field = get_fields_from_path(model_obj, field_name)[-1]
            model_obj = field.model
            internal_type = field.get_internal_type()
            disabled = getattr(settings, 'ADVANCED_FILTERS_DISABLE_FOR_FIELDS',
                               tuple())
            if field.name in disabled:
                logger.debug('Skipped lookup of operators for disabled fields')
                choices = []
            else:
                af_options = dict(AdvancedFilterQueryForm.OPERATORS)
                choices = []
                field_options = []
                if (
                    internal_type == 'CharField' or 
                    internal_type == 'EmailField' or 
                    internal_type == 'URLField'):
                    field_options = ["iexact", "icontains", "iregex", "isnull"]
                elif internal_type == 'BooleanField':
                    field_options = ["istrue", "isfalse", "isnull"]
                elif (
                    internal_type == 'PositiveIntegerField' or
                    internal_type == 'SmallIntegerField' or 
                    internal_type == 'PositiveSmallIntegerField' or
                    internal_type == 'BigIntegerField' or
                    internal_type == 'IntegerField' or
                    internal_type == 'FloatField' or
                    internal_type == 'DecimalField'):
                    field_options = ["lt", "gt", "lte", "gte", "isnull"]
                elif (
                    internal_type == 'DateTimeField' or
                    internal_type == 'DateField'):
                    field_options = ["range", "lt", "gt", "lte", "gte","isnull"]
                else:
                    field_options = af_options
                choices = [
                    {'key': option, 'value': af_options[option] } 
                    for option in field_options
                ]
            return self.render_json_response({'results': choices })
        except AttributeError as e:
            logger.debug("Invalid kwargs passed to view: %s", e)
            return self.render_json_response(
                {'error': "No installed app/model: %s" % model}, status=400)
        except (LookupError, FieldDoesNotExist) as e:
            logger.debug("Invalid kwargs passed to view: %s", e)
            return self.render_json_response(
                {'error': force_text(e)}, status=400)
