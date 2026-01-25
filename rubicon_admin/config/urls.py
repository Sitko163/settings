from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

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
    # Раздача статических файлов в режиме разработки
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # В production тоже раздаем статику через Django (если nginx не может)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)