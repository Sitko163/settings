from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    #path('login/', auth_views.LoginView.as_view(), name='login'),
    path('', include('flights.urls')),
    #path('api/', include('flights.api.urls')),
]

if settings.DEBUG:
    urlpatterns += [
        path('__debug__/', include('debug_toolbar.urls')),
    ]
