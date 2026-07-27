# -*- coding: utf-8 -*-
"""Namespace Socket.IO /telephony — Phase 11bis (fondations WebSocket).

Auth : JWT passé en query string (`?token=...`) à la connexion — les clients
Socket.IO n'envoient pas d'en-têtes personnalisés de façon portable côté
navigateur, contrairement au flux REST (cf. TELEPHONIE_INTEGRATION_PLAN.md §2.1).
Décodage manuel via `decode_token()` (pas `JWT_TOKEN_LOCATION=query_string`
globalement, pour ne pas affaiblir l'auth des routes REST).
"""
import uuid

from flask import request
from flask_jwt_extended import decode_token
from flask_socketio import Namespace, join_room, emit, disconnect

from app.models.tenant import Tenant
from app.models.tenant_user import TenantUser
from app.models.user import UserRole


class TelephonyNamespace(Namespace):
    def on_connect(self):
        token = request.args.get("token")
        if not token:
            disconnect()
            return False

        try:
            claims = decode_token(token)
        except Exception:
            disconnect()
            return False

        tenant_id_str = claims.get("tid")
        if not tenant_id_str:
            disconnect()
            return False

        try:
            tenant_id = uuid.UUID(tenant_id_str)
        except (ValueError, TypeError):
            disconnect()
            return False

        user_id = int(claims.get("sub"))
        is_super_admin = claims.get("role") == UserRole.ADMIN.value

        if is_super_admin:
            tenant = Tenant.query.filter_by(id=tenant_id, is_active=True).first()
        else:
            membership = TenantUser.query.filter_by(
                user_id=user_id, tenant_id=tenant_id, is_active=True
            ).first()
            tenant = membership.tenant if membership else None

        if not tenant or not tenant.is_active:
            disconnect()
            return False

        join_room(str(tenant_id))
        emit("connected", {"tenant_id": str(tenant_id)})

    def on_disconnect(self):
        pass
