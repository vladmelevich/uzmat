from django.urls import path
from . import views

app_name = 'uzmat'

urlpatterns = [
    path('', views.index, name='index'),
    path('ad/<slug:slug>/', views.ad_detail, name='ad_detail'),
    path('onboarding/', views.onboarding, name='onboarding'),
    path('auth/', views.auth, name='auth'),
    path('register/individual/', views.register_individual, name='register_individual'),
    path('register/company/', views.register_company, name='register_company'),
    path('profile/', views.profile, name='profile'),
    path('chats/', views.chats, name='chats'),
    path('chats/start/<int:ad_id>/', views.chat_start, name='chat_start'),
    path('chats/api/<int:thread_id>/send/', views.chat_send, name='chat_send'),
    path('chats/api/<int:thread_id>/poll/', views.chat_poll, name='chat_poll'),
    path('chats/api/message/<int:message_id>/edit/', views.chat_message_edit, name='chat_message_edit'),
    path('chats/api/message/<int:message_id>/delete/', views.chat_message_delete, name='chat_message_delete'),
    path('settings/', views.settings, name='settings'),
    path('parts/', views.parts_repair, name='parts_repair'),
    path('check-auth/', views.check_auth, name='check_auth'),
    path('logout/', views.logout_user, name='logout'),
    path('help/', views.help_page, name='help'),
    path('rules/', views.rules_page, name='rules'),
    path('safety/', views.safety_page, name='safety'),
    path('catalog/', views.catalog, name='catalog'),
    path('create/', views.create_ad, name='create_ad'),
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_use, name='terms_of_use'),
    path('sitemap/', views.sitemap, name='sitemap'),
    path('about/', views.about, name='about'),
    path('logistics/', views.logistics, name='logistics'),
    path('logistics/add/', views.add_cargo, name='add_cargo'),
    path('favorite/<int:ad_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('user/<int:user_id>/', views.user_profile, name='user_profile'),
    path('ad/<slug:slug>/edit/', views.edit_ad, name='edit_ad'),
    path('ad/<slug:slug>/delete/', views.delete_ad, name='delete_ad'),
    path('ad/<slug:slug>/toggle-status/', views.toggle_ad_status, name='toggle_ad_status'),
    path('ad/<slug:slug>/promote/', views.promote_ad, name='promote_ad'),
    path('ad/<slug:slug>/promote/info/', views.promote_info, name='promote_info'),
    path('verify/', views.verify_info, name='verify_info'),
    path('verify/renew/', views.verify_renew, name='verify_renew'),
    path('verify/moderation/', views.verify_moderation_list, name='verify_moderation_list'),
    path('verify/moderation/<int:request_id>/', views.verify_moderation_detail, name='verify_moderation_detail'),
    path('admin/notify/', views.admin_send_notification, name='admin_send_notification'),
    path('payment/click/webhook/', views.click_webhook, name='click_webhook'),
]




