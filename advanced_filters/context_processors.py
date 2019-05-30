from django.conf import settings


def advanced_filters(request):
    # return any necessary values
    return {
        'ADVANCED_FILTERS_MINIMUM_INPUT': getattr(settings,'ADVANCED_FILTERS_MINIMUM_INPUT', 2),
        'ADVANCED_FILTERS_QUIET_MILLIS': getattr(settings,'ADVANCED_FILTERS_QUIET_MILLIS',300)
    }