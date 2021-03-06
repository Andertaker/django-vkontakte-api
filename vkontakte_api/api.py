# -*- coding: utf-8 -*-
from django.conf import settings
from oauth_tokens.models import AccessToken
import requests

from oauth_tokens.api import ApiAbstractBase, Singleton
from vkontakte import VKError as VkontakteError, API


__all__ = ['api_call', 'VkontakteError']

SECURE_API_URL = 'https://api.vk.com/method/'
NO_TOKEN_METHODS = [
    'users.get',
    'users.search',
    'users.getFollowers',

    'groups.get',
    'groups.getById',
    'groups.getMembers',

    'wall.get',
    'wall.getById',
    'wall.search',
    'wall.getReposts',
    'wall.getComments',

    'photos.get',
    'photos.getAlbums',
    'photos.getProfile',
    'photos.getById',

    'likes.getList',
]


class VkontakteApi(ApiAbstractBase):

    __metaclass__ = Singleton

    provider = 'vkontakte'
    provider_social_auth = 'vk-oauth2'
    error_class = VkontakteError
    request_timeout = getattr(settings, 'VKONTAKTE_API_REQUEST_TIMEOUT', 1)

    def get_consistent_token(self):
        return getattr(settings, 'VKONTAKTE_API_ACCESS_TOKEN', None)

    def get_api(self, token):
        return API(token=token)

    def get_api_response(self, *args, **kwargs):
        return self.api.get(self.method, timeout=self.request_timeout, *args, **kwargs)

    def handle_error_code_5(self, e, *args, **kwargs):
        if self.user:
            raise e
        self.logger.info("Updating vkontakte access token, error %s, method: %s, recursion count: %d" %
                         (e, self.method, self.recursion_count))
        self.update_tokens()
        return self.repeat_call(*args, **kwargs)

    def handle_error_code_6(self, e, *args, **kwargs):
        # try access_token by another user
        self.logger.info("Vkontakte error 'Too many requests per second' on method: %s, recursion count: %d" % (
            self.method, self.recursion_count))
        self.used_access_tokens += [self.api.token]
        return self.repeat_call(*args, **kwargs)

    def handle_error_code_9(self, e, *args, **kwargs):
        self.logger.warning("Vkontakte flood control registered while executing method %s with params %s, \
            recursion count: %d" % (self.method, kwargs, self.recursion_count))
        self.used_access_tokens += [self.api.token]
        return self.sleep_repeat_call(*args, **kwargs)

    def handle_error_code_10(self, e, *args, **kwargs):
        self.logger.warning("Internal server error: Database problems, try later. Error registered while executing \
            method %s with params %s, recursion count: %d" % (self.method, kwargs, self.recursion_count))
        return self.sleep_repeat_call(*args, **kwargs)

    def handle_error_code_17(self, e, *args, **kwargs):
        # Validation required: please open redirect_uri in browser
        # TODO: cover with tests
        self.logger.warning("Request error: %s. Error registered while executing \
            method %s with params %s, recursion count: %d" % (e, self.method, kwargs, self.recursion_count))

        user = AccessToken.objects.get(access_token=self.api.token).user_credentials
        auth_request = AccessToken.objects.get_token_for_user('vkontakte', user).auth_request
        auth_request.form_action_domain = 'https://m.vk.com'

        response = auth_request.session.get(e.redirect_uri)
        try:
            method, action, data = auth_request.get_form_data_from_content(response.content)
        except:
            raise Exception("There is no any form in response: %s" % response.content)
        data = {'code': auth_request.additional}
        response = getattr(auth_request.session, method)(url=action, headers=auth_request.headers, data=data)

        if 'success' not in response.url:
            raise Exception("Wrong response. Can not handle VK error 17. response: %s" % response.content)

        return self.sleep_repeat_call(*args, **kwargs)

    def handle_error_code_500(self, e, *args, **kwargs):
        # strange HTTP error appears sometimes
        return self.sleep_repeat_call(*args, **kwargs)

    def handle_error_code_501(self, e, *args, **kwargs):
        # strange HTTP error appears sometimes
        return self.sleep_repeat_call(*args, **kwargs)

    def handle_error_code_502(self, e, *args, **kwargs):
        # strange HTTP error appears sometimes
        return self.sleep_repeat_call(*args, **kwargs)

    def handle_error_code_504(self, e, *args, **kwargs):
        # strange HTTP error appears sometimes
        return self.sleep_repeat_call(*args, **kwargs)



class ApiCallError(Exception):
     def __init__(self, value):
         self.value = value
     def __str__(self):
        return repr(self.value)



def api_call(method, *args, **kwargs):

    if method in NO_TOKEN_METHODS:
        url = SECURE_API_URL + method # 'https://api.vk.com/method/users.get'
        r = requests.get(url, params=kwargs)
        if r.status_code == 200:
            return r.json()["response"]
        else:
            raise ApiCallError(r.content)
    else:
        api = VkontakteApi()
        return api.call(method, *args, **kwargs)


def api_recursive_call(method, *args, **kwargs):

    if 'offset' not in kwargs:
        kwargs['offset'] = 0
    if 'count' not in kwargs:
        kwargs['count'] = 100

    response = {}
    while True:
        # print kwargs['offset']
        r = api_call(method, *args, **kwargs)
        kwargs['offset'] += kwargs['count']

        if not response: # first call
            response = r
        else:
            response['items'] += r['items']

        if 'count' in response:
            if len(response['items']) >= response['count']:
                # print "items: %s, count: %s" % (len(response['items']), response['count'])
                break
        # not all method return count
        if len(r['items']) == 0:
            # print "0 items"
            break

    return response
