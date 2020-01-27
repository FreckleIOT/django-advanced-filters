import logging

from django.db.models import Case, When
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.utils.translation import ugettext_lazy as _
from django.utils.module_loading import import_string
from urllib import parse
from django.utils.http import urlencode

from .forms import AdvancedFilterForm
from .models import AdvancedFilter


logger = logging.getLogger('advanced_filters.admin')

admin_instance = getattr(settings, 'ADVANCED_FILTERS_ADMIN_INSTANCE', None)
if admin_instance:
    site = import_string(admin_instance).site
else:
    site = admin.site


class AdvancedListFilters(admin.SimpleListFilter):
    """Allow filtering by stored advanced filters (selection by title)"""
    title = _('Advanced filters')

    parameter_name = '_afilter'

    def lookups(self, request, model_admin):
        if not model_admin:
            raise Exception('Cannot use AdvancedListFilters without a '
                            'model_admin')
        model_name = "%s.%s" % (model_admin.model._meta.app_label,
                                model_admin.model._meta.object_name)
        return AdvancedFilter.objects.filter_by_user_or_public(
            request.user).filter(
                model=model_name).order_by(
                    Case(When(created_by=request.user.id, then=0), default=1)
                ).values_list('id', 'title')

    def queryset(self, request, queryset):
        if self.value():
            filters = AdvancedFilter.objects.filter(id=self.value())
            if hasattr(filters, 'first'):
                advfilter = filters.first()
            if not advfilter:
                logger.error("AdvancedListFilters.queryset: Invalid filter id")
                return queryset
            query = advfilter.query
            logger.debug(query.__dict__)
            return queryset.filter(query).distinct()
        return queryset


class AdminAdvancedFiltersMixin(object):
    """ Generic AdvancedFilters mixin """
    advanced_change_list_template = "admin/advanced_filters.html"
    advanced_filter_form = AdvancedFilterForm

    def __init__(self, *args, **kwargs):
        super(AdminAdvancedFiltersMixin, self).__init__(*args, **kwargs)
        if self.change_list_template:
            self.original_change_list_template = self.change_list_template
        else:
            self.original_change_list_template = "admin/change_list.html"
        self.change_list_template = self.advanced_change_list_template
        # add list filters to filters
        self.list_filter = (AdvancedListFilters,) + tuple(self.list_filter)

    def save_advanced_filter(self, request, form):
        if form.is_valid():
            afilter = form.save(commit=False)
            afilter.created_by = request.user
            afilter.query = form.generate_query()
            afilter.save()
            afilter.users.add(request.user)
            messages.add_message(
                request, messages.SUCCESS,
                _('Advanced filter added successfully.')
            )
            qparams = request.GET.urlencode()
            qparams = dict(parse.parse_qsl(qparams))
            qparams['_afilter'] = afilter.id
            qparams = urlencode(sorted(qparams.items()))
            if ('_save_goto' in request.GET) or ('_save_goto' in request.POST):
                url = "{path}{qparams}".format(
                    path=request.path, qparams="?{qparams}".format(
                        id=afilter.id, qparams= qparams))
                return HttpResponseRedirect(url)
        elif request.method == "POST":
            logger.info('Failed saving advanced filter, params: %s', form.data)

    def adv_filters_handle(self, request, extra_context={}):
        data = request.POST if request.POST.get(
            'action') == 'advanced_filters' else None
        adv_filters_form = self.advanced_filter_form(
            data=data, model_admin=self, extra_form=True)
        extra_context.update({
            'original_change_list_template': self.original_change_list_template,
            'advanced_filters': adv_filters_form,
            'current_afilter': request.GET.get('_afilter'),
            'app_label': self.opts.app_label,
        })
        return self.save_advanced_filter(request, adv_filters_form)

    def changelist_view(self, request, extra_context=None):
        """Add advanced_filters form to changelist context"""
        if extra_context is None:
            extra_context = {}
        response = self.adv_filters_handle(request,
                                           extra_context=extra_context)
        if response:
            return response
        return super(AdminAdvancedFiltersMixin, self
                     ).changelist_view(request, extra_context=extra_context)


@admin.register(AdvancedFilter, site=site)
class AdvancedFilterAdmin(admin.ModelAdmin):
    model = AdvancedFilter
    form = AdvancedFilterForm
    extra = 0

    list_display = ('title', 'created_by', 'is_public')
    readonly_fields = ('created_by', 'model', 'created_at', )
    list_filter = (
        'is_public',
    )
    actions = ['delete_selected_filters']

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_add_permission(self, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if request.user == obj.created_by:
            return super().get_readonly_fields(request, obj=obj)
        return ['title', 'is_public'] + list(self.readonly_fields)

    def get_form(self, request, obj=None, **kwargs):
        AdminForm = super(AdvancedFilterAdmin, self).get_form(request, obj, **kwargs)

        class AdminFormWithRequest(AdminForm):
            def __new__(cls, *args, **kwargs):
                kwargs['readonly'] = request.user != obj.created_by
                return AdminForm(*args, **kwargs)

        return AdminFormWithRequest

    def save_model(self, request, new_object, *args, **kwargs):
        if new_object and not new_object.pk:
            new_object.created_by = request.user
        elif new_object.created_by != request.user:
            raise ValidationError('User does not own the filter')

        super(AdvancedFilterAdmin, self).save_model(
            request, new_object, *args, **kwargs)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        obj = AdvancedFilter.objects.get(id=object_id)
        if request.user != obj.created_by:
            extra_context = extra_context or {}
            extra_context['show_save_and_continue'] = False
            extra_context['show_save'] = False
            extra_context['readonly'] = True
        orig_response = super(AdvancedFilterAdmin, self).change_view(
            request, object_id, form_url, extra_context)
        qparams = request.GET.urlencode()
        if '_save_goto' in request.POST:
            obj = self.get_object(request, unquote(object_id))
            if obj:
                app, model = obj.model.split('.')
                path = resolve_url('admin:%s_%s_changelist' % (
                    app, model.lower()))
                url = "{path}{qparams}".format(
                    path=path, qparams="?{qparams}".format(
                        id=object_id, qparams=qparams))
                logger.info(url)
                return HttpResponseRedirect(url)
        return orig_response

    @staticmethod
    def user_has_permission(user):
        """Filters by user if not superuser or explicitly allowed in settings"""
        return user.is_superuser or not getattr(settings, "ADVANCED_FILTER_EDIT_BY_USER", True)

    def get_queryset(self, request):
        if self.user_has_permission(request.user):
            return super(AdvancedFilterAdmin, self).get_queryset(request)
        else:
            return self.model.objects.filter_by_user_or_public(
                request.user).order_by(
                    Case(When(created_by=request.user.id, then=0), default=1)
            )

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super(AdvancedFilterAdmin, self).has_change_permission(request)
        return (self.user_has_permission(request.user) or
                obj in self.model.objects.filter_by_user_or_public(request.user))

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return super(AdvancedFilterAdmin, self).has_delete_permission(request)
        return (self.user_has_permission(request.user) or
                obj in self.model.objects.filter_by_user(request.user))

    def delete_selected_filters(self, request, queryset):
        """
        Custom delete selected.

        A user should only be able to delete their own filters.
        """
        allowed_to_delete = queryset.filter(created_by=request.user)

        to_delete_count = allowed_to_delete.count()
        could_not_delete_count = queryset.exclude(created_by=request.user).count()

        allowed_to_delete.delete()

        if to_delete_count > 0:
            self.message_user(
                request,
                f'Successfully deleted {to_delete_count} filters.',
                level=messages.SUCCESS)

        if could_not_delete_count > 0:
            self.message_user(
                request,
                (f'Could not delete {could_not_delete_count} '
                 'filters as they do not belong to the current user.'),
                level=messages.WARNING)
