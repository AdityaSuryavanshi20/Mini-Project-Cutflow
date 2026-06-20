from catalog.models import CompanySettings

def company_settings(request):
    try:
        settings = CompanySettings.get()
    except Exception:
        settings = None
    return {'company_settings': settings}
