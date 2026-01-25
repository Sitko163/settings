JAZZMIN_SETTINGS = {
    "site_title": "5 Отряд",
    "site_logo": "images/logo.png",  # если есть логотип
    "welcome_sign": "Добро пожаловать в панель админа",

    "theme": "darkly",  # или "flatly", "cerulean" и т.д.

    "custom_css": "/admin/css/custom_admin.css",

    "topmenu_links": [
        {"name": "Главная", "url": "admin:index"},
        {"name": "Карта", "url": "/"},
        {"name": "Полеты", "url": "admin:your_app_flight_changelist"},  # замените your_app
    ],

    "show_ui_builder": False,
    "navigation_expanded": True,
    "sidebar_nav_small_text": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    },

    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "flights.Flight": "fas fa-plane",
        "flights.Pilot": "fas fa-user-pilot",
    },
}