from django.db.models import Count, Q, Case, When, IntegerField, Sum
from django.db.models.functions import TruncDate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime
from flights.models import Flight, FlightResultTypes, Pilot
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class PilotDetailView(APIView):
    def get(self, request, format=None):
        try:
            pilot_callname = request.query_params.get('pilot_callname')
            if not pilot_callname:
                return Response({'error': 'pilot_callname is required'}, status=status.HTTP_400_BAD_REQUEST)

            # Пробуем найти пилота (без учета регистра и с обработкой пробелов)
            pilot_callname_clean = pilot_callname.strip()
            try:
                pilot = Pilot.objects.get(callname__iexact=pilot_callname_clean)
            except Pilot.DoesNotExist:
                # Пробуем найти по точному совпадению
                try:
                    pilot = Pilot.objects.get(callname=pilot_callname_clean)
                except Pilot.DoesNotExist:
                    logger.error(f"Пилот не найден: '{pilot_callname_clean}'")
                    return Response({'error': f'Pilot not found: {pilot_callname_clean}'}, status=status.HTTP_404_NOT_FOUND)
            except Pilot.MultipleObjectsReturned:
                # Если несколько пилотов с таким именем, берем первого
                pilot = Pilot.objects.filter(callname__iexact=pilot_callname_clean).first()
                logger.warning(f"Найдено несколько пилотов с именем '{pilot_callname_clean}', используется первый")
        except Exception as e:
            logger.error(f"Ошибка при поиске пилота '{pilot_callname}': {e}", exc_info=True)
            return Response({'error': f'Error finding pilot: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Получаем все полеты пилота
        flights = Flight.objects.filter(pilot=pilot).select_related('pilot')

        # Общая статистика
        total_flights = flights.count()
        destroyed_flights = flights.filter(result=FlightResultTypes.DESTROYED).count()
        defeated_flights = flights.filter(result=FlightResultTypes.DEFEATED).count()
        not_defeated_flights = flights.filter(result=FlightResultTypes.NOT_DEFEATED).count()
        destruction_rate = (destroyed_flights / total_flights * 100) if total_flights > 0 else 0
        success_rate = ((destroyed_flights + defeated_flights) / total_flights * 100) if total_flights > 0 else 0

        # Группировка вылетов по целям
        flights_by_target = flights.values('target').annotate(
            total=Count('id'),
            destroyed=Sum(Case(
                When(result=FlightResultTypes.DESTROYED, then=1),
                output_field=IntegerField()
            )),
            defeated=Sum(Case(
                When(result=FlightResultTypes.DEFEATED, then=1),
                output_field=IntegerField()
            )),
            not_defeated=Sum(Case(
                When(result=FlightResultTypes.NOT_DEFEATED, then=1),
                output_field=IntegerField()
            )),
        ).order_by('-total')

        targets_data = []
        for target_stat in flights_by_target:
            target_name = target_stat['target'] or 'Без указания цели'
            destroyed = target_stat['destroyed'] if target_stat['destroyed'] is not None else 0
            defeated = target_stat['defeated'] if target_stat['defeated'] is not None else 0
            not_defeated = target_stat['not_defeated'] if target_stat['not_defeated'] is not None else 0
            total = target_stat['total']
            
            targets_data.append({
                'target': target_name,
                'total': total,
                'destroyed': destroyed,
                'defeated': defeated,
                'not_defeated': not_defeated,
                'destruction_rate': round((destroyed / total * 100) if total > 0 else 0, 2),
            })

        # Динамика по датам
        daily_stats = flights.annotate(flight_day=TruncDate('flight_date')).values('flight_day').annotate(
            total_flights=Count('id'),
            destroyed_flights=Sum(Case(
                When(result=FlightResultTypes.DESTROYED, then=1),
                output_field=IntegerField()
            )),
            defeated_flights=Sum(Case(
                When(result=FlightResultTypes.DEFEATED, then=1),
                output_field=IntegerField()
            )),
            not_defeated_flights=Sum(Case(
                When(result=FlightResultTypes.NOT_DEFEATED, then=1),
                output_field=IntegerField()
            )),
        ).order_by('flight_day')

        daily_trend = []
        for stat in daily_stats:
            destroyed = stat['destroyed_flights'] if stat['destroyed_flights'] is not None else 0
            defeated = stat['defeated_flights'] if stat['defeated_flights'] is not None else 0
            not_defeated = stat['not_defeated_flights'] if stat['not_defeated_flights'] is not None else 0
            total = stat['total_flights']
            
            daily_trend.append({
                'date': stat['flight_day'].isoformat() if stat['flight_day'] else None,
                'total_flights': total,
                'destroyed_flights': destroyed,
                'defeated_flights': defeated,
                'not_defeated_flights': not_defeated,
            })

        # Статистика по БК (боеприпасы/компоненты)
        # Дроны
        drone_usage = flights.exclude(drone__isnull=True).exclude(drone='').values('drone').annotate(
            count=Count('id')
        ).order_by('-count')
        
        drones_usage_list = []
        for item in drone_usage:
            drones_usage_list.append({
                'drone': item['drone'],
                'count': item['count']
            })
        
        # Боевая часть (explosive_type)
        explosive_type_usage = flights.exclude(explosive_type__isnull=True).exclude(explosive_type='').values('explosive_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        explosive_types_list = []
        for item in explosive_type_usage:
            explosive_types_list.append({
                'explosive_type': item['explosive_type'],
                'count': item['count']
            })
        
        # Запалы (explosive_device)
        explosive_device_usage = flights.exclude(explosive_device__isnull=True).exclude(explosive_device='').values('explosive_device').annotate(
            count=Count('id')
        ).order_by('-count')
        
        explosive_devices_list = []
        for item in explosive_device_usage:
            explosive_devices_list.append({
                'explosive_device': item['explosive_device'],
                'count': item['count']
            })
        
        # Детальный список всех вылетов (ограничиваем количество для производительности)
        flights_list = []
        try:
            flights_queryset = flights.order_by('-flight_date', '-flight_time')[:1000]  # Ограничиваем до 1000 записей
            for flight in flights_queryset:
                try:
                    flights_list.append({
                        'id': str(flight.id),
                        'number': flight.number,
                        'flight_date': flight.flight_date.isoformat() if flight.flight_date else None,
                        'flight_time': flight.flight_time.isoformat() if flight.flight_time else None,
                        'target': flight.target or '',
                        'drone': flight.drone or '',
                        'result': flight.result or '',
                        'coordinates': flight.coordinates or '',
                        'distance': flight.distance or '',
                        'comment': flight.comment or '',
                    })
                except Exception as e:
                    logger.warning(f"Ошибка при обработке полета {flight.id}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Ошибка при получении списка полетов: {e}", exc_info=True)

        try:
            return Response({
                'pilot': {
                    'id': str(pilot.id),
                    'callname': pilot.callname,
                    'tg_id': pilot.tg_id,
                },
                'statistics': {
                    'total_flights': total_flights,
                    'destroyed_flights': destroyed_flights,
                    'defeated_flights': defeated_flights,
                    'not_defeated_flights': not_defeated_flights,
                    'destruction_rate': round(destruction_rate, 2),
                    'success_rate': round(success_rate, 2),
                },
                'flights_by_target': targets_data,
                'daily_trend': daily_trend,
                'flights': flights_list,
                'bc_usage': {
                    'drones': drones_usage_list,
                    'explosive_types': explosive_types_list,
                    'explosive_devices': explosive_devices_list,
                },
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Ошибка при формировании ответа для пилота {pilot.callname}: {e}", exc_info=True)
            return Response({
                'error': f'Error generating response: {str(e)}',
                'pilot': {
                    'id': str(pilot.id),
                    'callname': pilot.callname,
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

