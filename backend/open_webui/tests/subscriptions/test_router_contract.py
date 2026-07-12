from open_webui.routers import subscriptions


def test_router_exposes_user_and_admin_paths():
    paths = {route.path for route in subscriptions.router.routes}

    assert '/me' in paths
    assert '/usage' in paths
    assert '/plans' in paths
    assert '/redeem' in paths
    assert '/gift-cards/pending' in paths
    assert '/gift-cards/{grant_id}/claim' in paths
    assert '/records' in paths
    assert '/billing-address' in paths
    assert '/admin/plans' in paths
    assert '/admin/models' in paths
    assert '/admin/models/bulk' in paths
    assert '/admin/codes' in paths
    assert '/admin/codes/{code_id}' in paths
    assert '/admin/gift-cards' in paths
    assert '/admin/gift-cards/{grant_id}' in paths
    assert '/admin/users' in paths
    assert '/admin/users/{user_id}' in paths
    assert '/admin/usage' in paths
    assert '/admin/ledger' in paths
