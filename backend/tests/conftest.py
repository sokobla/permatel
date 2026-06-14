import pytest
from datetime import datetime, timedelta
from app import create_app, db as _db
from app.models.user import User, UserRole
from app.models.agent_securite import AgentSecurite
from app.models.user_session import UserSession, SessionStatus
from app.models.token_blocklist import TokenBlocklist
from app.models.tenant import Tenant


@pytest.fixture(scope="session")
def app():
    """Crée une instance Flask en mode test avec SQLite en mémoire."""
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    """Nettoie toutes les tables avant et après chaque test."""
    with app.app_context():
        # Nettoyer avant le test
        _db.session.remove()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()
        
        yield _db
        
        # Nettoyer après le test
        _db.session.remove()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def default_tenant(db):
    """Crée un tenant par défaut pour les tests."""
    t = Tenant(code="CORE", nom="Tenant Principal", slug="core")
    db.session.add(t)
    db.session.commit()
    return t

@pytest.fixture
def user_permanencier(db, default_tenant):
    """Crée un utilisateur PERMANENCIER actif."""
    u = User(
        username="permanencier1",
        email="perm1@permatel.ma",
        nom="Martin",
        prenom="Alice",
        role=UserRole.PERMANENCIER,
        is_active=True,
    )
    u.set_password("Password123!")
    u.tenants.append(default_tenant)
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def agent_securite(db, default_tenant):
    """Crée un agent de sécurité actif pour les tests de planning."""
    agent = AgentSecurite(
        matricule="AGENT001",
        nom="Agent",
        prenom="Security",
        telephone="0600000000",
        email="agent1@permatel.ma",
        tenant_id=default_tenant.id,
        is_active=True,
    )
    db.session.add(agent)
    db.session.commit()
    return agent


@pytest.fixture
def user_manager(db, default_tenant):
    """Crée un utilisateur MANAGER actif."""
    u = User(
        username="manager1",
        email="manager1@permatel.ma",
        nom="Bernard",
        prenom="Paul",
        role=UserRole.MANAGER,
        is_active=True,
    )
    u.set_password("Password123!")
    u.tenants.append(default_tenant)
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def user_admin(db, default_tenant):
    """Crée un utilisateur ADMIN actif."""
    u = User(
        username="admin1",
        email="admin1@permatel.ma",
        nom="Dupont",
        prenom="Jean",
        role=UserRole.ADMIN,
        is_active=True,
    )
    u.set_password("Password123!")
    u.tenants.append(default_tenant)
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def user_inactive(db, default_tenant):
    """Crée un utilisateur désactivé."""
    u = User(
        username="inactif1",
        email="inactif1@permatel.ma",
        nom="Absent",
        prenom="Bob",
        role=UserRole.PERMANENCIER,
        is_active=False,
    )
    u.set_password("Password123!")
    u.tenants.append(default_tenant)
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def tokens_permanencier(client, user_permanencier):
    """Effectue un login et retourne les tokens + session_id."""
    resp = client.post("/api/auth/login", json={
        "username": "permanencier1",
        "password": "Password123!",
    })
    data = resp.get_json()
    return {
        "access_token":  data["access_token"],
        "refresh_token": data["refresh_token"],
        "session_id":    data["session_id"],
        "user":          data["user"],
    }


@pytest.fixture
def auth_headers(tokens_permanencier):
    """Header Authorization prêt à l'emploi avec l'access token."""
    return {"Authorization": f"Bearer {tokens_permanencier['access_token']}"}


@pytest.fixture
def refresh_headers(tokens_permanencier):
    """Header Authorization avec le refresh token."""
    return {"Authorization": f"Bearer {tokens_permanencier['refresh_token']}"}