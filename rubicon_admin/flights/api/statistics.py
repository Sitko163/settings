from django.db.models import Count, Q, Case, When, IntegerField, Sum, Avg
from django.db.models.functions import TruncDate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta
from flights.models import Flight, FlightResultTypes
from django.utils import timezone
from collections import defaultdict
import logging
import re

logger = logging.getLogger(__name__)

def normalize_drone_for_display(drone_name):
    """Нормализует название дрона для отображения в статистике.
    Преобразует все варианты КВН в два: КВН или КВН-Т"""
    if not drone_name:
        return drone_name
    drone_str = str(drone_name).strip()
    if not drone_str:
        return drone_name
    
    # Приводим к нижнему регистру для проверки
    drone_lower = drone_str.lower()
    
    # КВН - преобразуем все варианты в два: КВН или КВН-Т
    # Проверяем наличие "квн" в строке (без учета регистра)
    if 'квн' in drone_lower:
        # Находим позицию "квн" в строке
        kvn_pos = drone_lower.find('квн')
        if kvn_pos != -1:
            # Берем все после "квн" (3 символа: к, в, н)
            substring_after_kvn = drone_lower[kvn_pos + 3:]
            # Убираем все символы кроме букв и цифр для проверки наличия "т"
            # Это покроет все варианты: квн-т, квн-16т, квн-16-т, квн-23т, квн-23-т, квн 16 т, квнт и т.д.
            cleaned = re.sub(r'[^а-яё0-9]', '', substring_after_kvn)
            if 'т' in cleaned:
                return 'КВН-Т'
        return 'КВН'
    
    # Для остальных дронов возвращаем как есть
    return drone_name

class StatisticsView(APIView):
    def get(self, request, format=None):
        logger.debug("=== НАЧАЛО StatisticsView ===")
        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')
        pilot_callname = request.query_params.get('pilot_callname')
        drone_type = request.query_params.get('drone_type')
        logger.debug(
            f"Параметры запроса: date_from={date_from_str}, date_to={date_to_str}, pilot_callname={pilot_callname}, drone_type={drone_type}")

        flights = Flight.objects.select_related('pilot')

        if date_from_str:
            try:
                date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
                flights = flights.filter(flight_date__gte=date_from)
                logger.debug(f"Фильтр по дате с: {date_from}")
            except ValueError:
                logger.warning(f"Неверный формат date_from: {date_from_str}")
                pass # Или return Response(..., status=status.HTTP_400_BAD_REQUEST)

        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
                flights = flights.filter(flight_date__lte=date_to)
                logger.debug(f"Фильтр по дате по: {date_to}")
            except ValueError:
                logger.warning(f"Неверный формат date_to: {date_to_str}")
                pass # Или return Response(..., status=status.HTTP_400_BAD_REQUEST)

        # --- ИЗМЕНЕНО: Фильтруем по callname ---
        if pilot_callname:
            # Используем icontains для нечеткого поиска (без учета регистра и частичное совпадение)
            # или __iexact для точного совпадения без учета регистра
            # flights = flights.filter(pilot__callname__iexact=pilot_callname)
            flights = flights.filter(pilot__callname__icontains=pilot_callname)
            logger.debug(f"Фильтр по позывному пилота: {pilot_callname}")

        if drone_type:
            # Нормализуем значение фильтра
            normalized_filter_drone = normalize_drone_for_display(drone_type)
            # Находим все варианты дронов в текущем queryset, которые нормализуются в выбранное значение
            all_drones_in_queryset = flights.values_list('drone', flat=True).distinct()
            matching_drones = [
                d for d in all_drones_in_queryset
                if normalize_drone_for_display(d) == normalized_filter_drone
            ]
            if matching_drones:
                flights = flights.filter(drone__in=matching_drones)
                logger.debug(f"Фильтр по типу дрона: {drone_type} (нормализовано: {normalized_filter_drone}, найдено вариантов: {len(matching_drones)})")
            else:
                # Если не найдено совпадений, фильтруем по точному значению (на случай, если это не КВН)
                flights = flights.filter(drone=drone_type)
                logger.debug(f"Фильтр по типу дрона (точное совпадение): {drone_type}")

        # --- Остальная логика остается без изменений ---
        total_flights = flights.count()
        logger.debug(f"Всего полетов после фильтрации: {total_flights}")
        stats_data = {}
        destroyed_flights_count = flights.filter(result=FlightResultTypes.DESTROYED).count()
        defeated_flights_count = flights.filter(result=FlightResultTypes.DEFEATED).count()
        not_defeated_flights_count = flights.filter(result=FlightResultTypes.NOT_DEFEATED).count()
        destruction_rate = (destroyed_flights_count / total_flights * 100) if total_flights > 0 else 0
        # Процент успеха = (уничтожено + поражено) / всего * 100
        success_rate = ((destroyed_flights_count + defeated_flights_count) / total_flights * 100) if total_flights > 0 else 0
        stats_data['kpi'] = {
            'total_flights': total_flights,
            'destroyed_flights': destroyed_flights_count,
            'defeated_flights': defeated_flights_count,
            'not_defeated_flights': not_defeated_flights_count,
            'destruction_rate_percent': round(destruction_rate, 2),
            'success_rate_percent': round(success_rate, 2),
        }

        # Исключаем пилотов с именем, начинающимся с "Неизвестный_"
        pilot_stats = flights.exclude(
            pilot__callname__istartswith='Неизвестный_'
        ).values('pilot__id', 'pilot__callname').annotate(
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
        ).order_by('-total_flights')
        pilot_stats_list = []
        for stat in pilot_stats:
            destroyed = stat['destroyed_flights'] if stat['destroyed_flights'] is not None else 0
            defeated = stat['defeated_flights'] if stat['defeated_flights'] is not None else 0
            not_defeated = stat['not_defeated_flights'] if stat['not_defeated_flights'] is not None else 0
            total = stat['total_flights']
            pilot_destruction_rate = (destroyed / total * 100) if total > 0 else 0
            pilot_success_rate = ((destroyed + defeated) / total * 100) if total > 0 else 0
            stat['destruction_rate_percent'] = round(pilot_destruction_rate, 2)
            stat['success_rate_percent'] = round(pilot_success_rate, 2)
            pilot_stats_list.append(stat)
        stats_data['pilots'] = pilot_stats_list

        # Получаем статистику по дронам и нормализуем названия
        # Сначала получаем все записи с дронами для группировки
        drone_flights = flights.values('drone', 'pilot', 'result').annotate(
            count=Count('id')
        )
        
        # Группируем по нормализованным названиям дронов
        drone_stats_dict = {}
        for flight_data in drone_flights:
            original_drone = flight_data['drone']
            normalized_drone = normalize_drone_for_display(original_drone)
            
            if normalized_drone not in drone_stats_dict:
                drone_stats_dict[normalized_drone] = {
                    'drone': normalized_drone,
                    'total_flights': 0,
                    'destroyed_flights': 0,
                    'defeated_flights': 0,
                    'not_defeated_flights': 0,
                    'pilots_involved': set()
                }
            
            count = flight_data['count']
            result = flight_data['result']
            pilot_id = flight_data['pilot']
            
            # Суммируем статистику
            drone_stats_dict[normalized_drone]['total_flights'] += count
            if result == FlightResultTypes.DESTROYED:
                drone_stats_dict[normalized_drone]['destroyed_flights'] += count
            elif result == FlightResultTypes.DEFEATED:
                drone_stats_dict[normalized_drone]['defeated_flights'] += count
            elif result == FlightResultTypes.NOT_DEFEATED:
                drone_stats_dict[normalized_drone]['not_defeated_flights'] += count
            
            # Собираем уникальных пилотов
            if pilot_id:
                drone_stats_dict[normalized_drone]['pilots_involved'].add(pilot_id)
        
        # Преобразуем в список и вычисляем проценты
        drone_stats_list = []
        for normalized_drone, stat in drone_stats_dict.items():
            destroyed = stat['destroyed_flights']
            defeated = stat['defeated_flights']
            not_defeated = stat['not_defeated_flights']
            total = stat['total_flights']
            drone_destruction_rate = (destroyed / total * 100) if total > 0 else 0
            drone_success_rate = ((destroyed + defeated) / total * 100) if total > 0 else 0
            
            drone_stats_list.append({
                'drone': normalized_drone,
                'total_flights': total,
                'destroyed_flights': destroyed,
                'defeated_flights': defeated,
                'not_defeated_flights': not_defeated,
                'pilots_involved': len(stat['pilots_involved']),
                'destruction_rate_percent': round(drone_destruction_rate, 2),
                'success_rate_percent': round(drone_success_rate, 2)
            })
        
        # Сортируем по общему количеству полетов
        drone_stats_list.sort(key=lambda x: x['total_flights'], reverse=True)
        stats_data['drones'] = drone_stats_list

        result_counts = flights.values('result').annotate(count=Count('id')).order_by('-count')
        results_dict = {item['result']: item['count'] for item in result_counts}
        final_results_dict = {
            FlightResultTypes.DESTROYED: results_dict.get(FlightResultTypes.DESTROYED, 0),
            FlightResultTypes.DEFEATED: results_dict.get(FlightResultTypes.DEFEATED, 0),
            FlightResultTypes.NOT_DEFEATED: results_dict.get(FlightResultTypes.NOT_DEFEATED, 0),
        }
        stats_data['results_breakdown'] = final_results_dict

        # Статистика по уничтоженным целям (общая для всех пилотов)
        target_stats = flights.exclude(
            target__isnull=True
        ).exclude(
            target=''
        ).filter(
            result=FlightResultTypes.DESTROYED
        ).values('target').annotate(
            destroyed_count=Count('id')
        ).order_by('-destroyed_count')[:20]  # Топ-20 целей
        
        target_stats_list = []
        for stat in target_stats:
            target_stats_list.append({
                'target': stat['target'],
                'destroyed_count': stat['destroyed_count']
            })
        stats_data['targets'] = target_stats_list

        # Статистика по целям для каждого пилота (только если фильтруется по конкретному пилоту)
        if pilot_callname:
            # Если указан фильтр по пилоту, показываем результаты по целям только для этого пилота
            pilot_stats_for_targets = flights.exclude(
                pilot__callname__istartswith='Неизвестный_'
            ).exclude(
                target__isnull=True
            ).exclude(
                target=''
            ).filter(
                result=FlightResultTypes.DESTROYED,
                pilot__callname__icontains=pilot_callname
            ).values(
                'pilot__id', 
                'pilot__callname', 
                'target'
            ).annotate(
                destroyed_count=Count('id')
            ).order_by('pilot__callname', '-destroyed_count')
            
            # Группируем по пилотам
            pilots_targets_dict = defaultdict(list)
            
            for stat in pilot_stats_for_targets:
                pilot_name = stat['pilot__callname']
                pilot_id = stat['pilot__id']
                target_name = stat['target']
                destroyed_count = stat['destroyed_count']
                
                pilots_targets_dict[pilot_name].append({
                    'pilot_id': pilot_id,
                    'target': target_name,
                    'destroyed_count': destroyed_count
                })
            
            # Преобразуем в список и сортируем по общему количеству уничтожений
            pilot_targets_list = []
            for pilot_name, targets in pilots_targets_dict.items():
                total_destroyed = sum(t['destroyed_count'] for t in targets)
                # Получаем pilot_id из первого элемента (все они одинаковые для одного пилота)
                pilot_id = targets[0]['pilot_id'] if targets else None
                pilot_targets_list.append({
                    'pilot_name': pilot_name,
                    'pilot_id': pilot_id,
                    'targets': sorted(targets, key=lambda x: x['destroyed_count'], reverse=True),
                    'total_destroyed': total_destroyed
                })
            
            # Сортируем пилотов по общему количеству уничтожений целей
            pilot_targets_list.sort(key=lambda x: x['total_destroyed'], reverse=True)
            stats_data['pilot_targets'] = pilot_targets_list
        else:
            # Если фильтр по пилоту не указан, не возвращаем данные
            stats_data['pilot_targets'] = []

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
        daily_stats_list = []
        for stat in daily_stats:
            destroyed = stat['destroyed_flights'] if stat['destroyed_flights'] is not None else 0
            defeated = stat['defeated_flights'] if stat['defeated_flights'] is not None else 0
            not_defeated = stat['not_defeated_flights'] if stat['not_defeated_flights'] is not None else 0
            total = stat['total_flights']
            day_destruction_rate = (destroyed / total * 100) if total > 0 else 0
            daily_stats_list.append({
                'date': stat['flight_day'].isoformat(),
                'total_flights': total,
                'destroyed_flights': destroyed,
                'defeated_flights': defeated,
                'not_defeated_flights': not_defeated,
                'destruction_rate_percent': round(day_destruction_rate, 2)
            })
        stats_data['daily_trend'] = daily_stats_list

        flights_with_coords = flights.exclude(
            Q(lat_wgs84__isnull=True) |
            Q(lon_wgs84__isnull=True)
        ).values(
            'lat_wgs84',
            'lon_wgs84',
            'result'
        )
        heatmap_points = []
        for flight in flights_with_coords:
            lat = flight['lat_wgs84']
            lon = flight['lon_wgs84']
            result = flight['result']
            if lat == 90.0 and lon == 0.0:
                continue
            weight = 0.5
            if result == FlightResultTypes.DEFEATED:
                weight = 1.5
            elif result == FlightResultTypes.DESTROYED:
                weight = 2.5
            heatmap_points.append({
                'lat': lat,
                'lng': lon,
                'weight': weight
            })
        stats_data['heatmap_points'] = heatmap_points

        most_active_pilot = None
        if pilot_stats_list:
            most_active_pilot = pilot_stats_list[0]['pilot__callname']
        most_popular_drone = None
        if drone_stats_list:
            most_popular_drone = drone_stats_list[0]['drone']
        stats_data['summary'] = {
            'most_active_pilot': most_active_pilot,
            'most_popular_drone': most_popular_drone,
        }

        latest_flights = flights.order_by('-flight_date', '-flight_time')[:50]
        flights_table_data = []
        for flight in latest_flights:
            flights_table_data.append({
                'id': str(flight.id),
                'number': flight.number,
                'pilot_name': flight.pilot.callname if flight.pilot else 'N/A',
                'drone': normalize_drone_for_display(flight.drone),
                'flight_date': flight.flight_date.isoformat() if flight.flight_date else None,
                'flight_time': flight.flight_time.isoformat() if flight.flight_time else None,
                'target': flight.target,
                'result': flight.result,
                'comment': flight.comment,
            })
        stats_data['flights_table'] = flights_table_data

        logger.debug("=== КОНЕЦ StatisticsView УСПЕШНО ===")
        return Response(stats_data, status=status.HTTP_200_OK)
