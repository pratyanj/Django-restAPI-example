from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET', 'POST', 'PUT', 'DELETE'])
# @api_view(['GET'])
def index(request):
    courses = {
        'courses': [
            {
                'id': 1,
                'title': 'Python',
                'description': 'Python is a programming language',
                'price': 100
            },
            {
                'id': 2,
                'title': 'JavaScript',
                'description': 'JavaScript is a programming language',
                'price': 200
            },
            {
                'id': 3,
                'title': 'Django',
                'description': 'Django is a web framework',
                'price': 300
            }
        ]
    }
    if request.method == "GET":
        print("GET method called")
    elif request.method == "POST":
        print("POST method called")
    elif request.method == "PUT":
        print("PUT method called")
    elif request.method == "DELETE":
        print("DELETE method called")
    return Response(courses)