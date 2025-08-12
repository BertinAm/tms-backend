class CORSMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Get the origin from the request
        origin = request.META.get('HTTP_ORIGIN', '')
        
        # Allow specific origins
        allowed_origins = [
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'https://tms-system-d361ed05cf4f.herokuapp.com',
            'https://tms-frontend.herokuapp.com',
            'https://*.herokuapp.com',
            'https://*.onrender.com'
        ]
        
        # Check if origin is allowed
        if any(origin.endswith(allowed_origin.replace('*', '')) for allowed_origin in allowed_origins if '*' in allowed_origin) or origin in allowed_origins:
            response["Access-Control-Allow-Origin"] = origin
        else:
            response["Access-Control-Allow-Origin"] = "*"
        
        # Add CORS headers
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept, Origin"
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Max-Age"] = "86400"  # 24 hours
        
        # Handle preflight requests
        if request.method == "OPTIONS":
            response.status_code = 200
            
        return response