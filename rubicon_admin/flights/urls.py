from django.urls import path
from flights import views
from django.contrib.auth import views as auth_views
from flights.api import flights_total, statistics, schedule, rating, forced_cache_flights, pilot_detail, reports, pilot_export, filters, target_rating

urlpatterns = [
    path('', views.map_view, name='map'),           # главная страница с картой
    path('statistics/', views.statistics_view, name='statistics-page'),
    path('schedule/', views.schedule_view, name='schedule-page'),
    path('rating/', views.rating_view, name='schedule-page'),
    path('reports/', views.reports_view, name='reports-page'),

    path('api/flights/', flights_total.FlightsListView.as_view(), name='flights-list'),  # API для полетов
    path('api/force_cache_flights/', forced_cache_flights.FlightsListViewWithForcedCache.as_view(), name='cache_flights'),  # API для полетов
    path('api/statistics/', statistics.StatisticsView.as_view(), name='statistics'), # Добавляем новый endpoint
    path('api/pilot_detail/', pilot_detail.PilotDetailView.as_view(), name='pilot-detail'),
    path('api/pilot_export/excel/', pilot_export.PilotExportExcelView.as_view(), name='pilot-export-excel'),
    path('api/filters/', filters.FiltersDataView.as_view(), name='filters-data'),
    path('api/schedule/', schedule.ScheduleAPIView.as_view(), name='schedule'),
    path('api/rating/', rating.PilotRatingView.as_view(), name='rating'),
    path('api/target_rating/', target_rating.TargetRatingView.as_view(), name='target-rating'),
    path('api/reports/data/', reports.ReportsDataView.as_view(), name='reports-data'),
    path('api/reports/export/excel/', views.export_report_excel, name='export-report-excel'),
    path('api/reports/export/pdf/', views.export_report_pdf, name='export-report-pdf'),
    path('debug/ip/', views.debug_ip, name='debug_ip'),

    path('login/', views.login_view, name='login'),
    path('login/standard/', views.standard_login_view, name='standard_login'),
    path('login/telegram/', views.telegram_login_step1, name='telegram_login_step1'),
    path('login/telegram/code/', views.telegram_login_step2, name='telegram_login_step2'),
    path('login/telegram/cancel/', views.telegram_login_cancel, name='telegram_login_cancel'),
    path('log-out/', views.logout_view, name='logout'),
    #path('protected/', views.my_protected_view, name='protected'),
]