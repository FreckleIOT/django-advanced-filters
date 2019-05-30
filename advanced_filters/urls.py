from django.conf.urls import url

from advanced_filters.views import GetFieldChoices, GetOperatorChoices

urlpatterns = [
    url(r'^field_choices/(?P<model>.+)/(?P<field_name>.+)/?',
        GetFieldChoices.as_view(),
        name='afilters_get_field_choices'),

    # only to allow building dynamically
    url(r'^field_choices/$',
        GetFieldChoices.as_view(),
        name='afilters_get_field_choices'),

    url(r'^operator_choices/(?P<model>.+)/(?P<field_name>.+)/?',
        GetOperatorChoices.as_view(),
        name='afilters_get_operator_choices'),

    url(r'^operator_choices/$',
        GetOperatorChoices.as_view(),
        name='afilters_get_operator_choices'),
]
