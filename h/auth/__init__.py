# -*- coding: utf-8 -*-

"""Authentication configuration."""

import logging

from pyramid.authentication import (RemoteUserAuthenticationPolicy,
                                    SessionAuthenticationPolicy)
from pyramid_multiauth import MultiAuthenticationPolicy

from h.auth.policy import AuthenticationPolicy, TokenAuthenticationPolicy
from h.auth.util import groupfinder

__all__ = (
    'DEFAULT_POLICY',
    'WEBSOCKET_POLICY',
)

log = logging.getLogger(__name__)

PROXY_POLICY = RemoteUserAuthenticationPolicy(environ_key='HTTP_X_FORWARDED_USER',
                                              callback=groupfinder)
SESSION_POLICY = SessionAuthenticationPolicy(callback=groupfinder)
TOKEN_POLICY = TokenAuthenticationPolicy(callback=groupfinder)

DEFAULT_POLICY = AuthenticationPolicy(api_policy=TOKEN_POLICY,
                                      fallback_policy=SESSION_POLICY)
WEBSOCKET_POLICY = MultiAuthenticationPolicy([TOKEN_POLICY, SESSION_POLICY])


def auth_domain(request):
    """Return the value of the h.auth_domain config settings.

    Falls back on returning request.domain if h.auth_domain isn't set.

    """
    return request.registry.settings.get('h.auth_domain', request.domain)


def includeme(config):
    global DEFAULT_POLICY
    global WEBSOCKET_POLICY

    if config.registry.settings.get('h.proxy_auth'):
        log.warn('Enabling proxy authentication mode: you MUST ensure that '
                 'the X-Forwarded-User request header can ONLY be set by '
                 'trusted downstream reverse proxies! Failure to heed this '
                 'warning will result in ALL DATA stored by this service '
                 'being available to ANYONE!')

        DEFAULT_POLICY = AuthenticationPolicy(api_policy=TOKEN_POLICY,
                                              fallback_policy=PROXY_POLICY)
        WEBSOCKET_POLICY = MultiAuthenticationPolicy([TOKEN_POLICY,
                                                      PROXY_POLICY])

    # Set the default authentication policy. This can be overridden by modules
    # that include this one.
    config.set_authentication_policy(DEFAULT_POLICY)

    # Allow retrieval of the auth_domain from the request object.
    config.add_request_method(auth_domain, name='auth_domain', reify=True)

    # Allow retrieval of the auth token (if present) from the request object.
    config.add_request_method('.tokens.auth_token', reify=True)
