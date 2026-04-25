"""
URL configuration for chitara project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from song_gen.views import (
    suno_callback, 
    landing_view, 
    login_view,
    register_view,
    logout_view,
    library_view, 
    generate_view, 
    shared_song_view, 
    delete_song_view,
    generation_status_view,
    song_status_api,
    library_search_api
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/suno/callback/', suno_callback, name='suno_callback'),
    
    # Frontend Routes
    path('', landing_view, name='landing'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('library/', library_view, name='library'),
    path('generate/', generate_view, name='generate'),
    path('generation_status/<int:id>/', generation_status_view, name='generation_status'),
    path('api/status/<int:id>/', song_status_api, name='song_status_api'),
    path('api/library/search/', library_search_api, name='library_search_api'),
    path('shared/<int:id>/', shared_song_view, name='shared_song'),
    path('delete/<int:id>/', delete_song_view, name='delete_song'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
