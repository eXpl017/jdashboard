def test_root_returns_dashboard_html(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Japan Cybersecurity Jobs" in response.text
    assert "/static/app.css" in response.text
    assert "/static/app.js" in response.text
