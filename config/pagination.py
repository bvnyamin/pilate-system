from django.core.paginator import EmptyPage, Paginator


class ListPaginator(Paginator):
    def validate_number(self, number):
        try:
            return super().validate_number(number)
        except EmptyPage:
            if int(number) > self.num_pages:
                return self.num_pages
            raise
