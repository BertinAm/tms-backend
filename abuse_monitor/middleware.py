class CORSMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Get the origin from the request
        origin = request.META.get('HTTP_ORIGIN', '')
        
        # Allow all origins for now to debug the issue
        response["Access-Control-Allow-Origin"] = "*"
        
        # Add CORS headers
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept, Origin"
        response["Access-Control-Allow-Credentials"] = "false"
        response["Access-Control-Max-Age"] = "86400"  # 24 hours
        
        # Handle preflight requests
        if request.method == "OPTIONS":
            response.status_code = 200
            
        return response