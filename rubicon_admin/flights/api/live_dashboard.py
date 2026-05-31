from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from flights.utils.live_flight import get_dashboard_live_flights


class LiveDashboardAPIView(APIView):
    """Оперативные вылеты для дашборда (в работе + за 24 ч, МСК)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        region_id = request.query_params.get('region') or request.query_params.get('weather_region')
        return Response(get_dashboard_live_flights(weather_region_id=region_id))
