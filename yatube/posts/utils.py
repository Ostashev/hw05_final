from django.core.paginator import Paginator


PAGINATION: int = 10


def get_page_obj(request, list_of_objects):
    paginator = Paginator(list_of_objects, PAGINATION)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return page_obj
