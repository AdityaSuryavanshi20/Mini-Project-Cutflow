class RoleMiddleware:
    """Attach role to request for easy template access"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            request.user_role = request.user.profile.role
        else:
            request.user_role = None
        return self.get_response(request)
