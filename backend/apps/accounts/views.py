from rest_framework.generics import RetrieveAPIView

from .serializers import CurrentUserSerializer


class CurrentUserView(RetrieveAPIView):
    serializer_class = CurrentUserSerializer

    def get_object(self):
        return self.request.user
