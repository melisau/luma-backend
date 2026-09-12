TOKEN='event-a-token-123456789012345678901234'
def test_opening_style_persists(client,admin_headers):
    url=f'/api/admin/events/{TOKEN}/invitation'
    assert client.get(f'/api/events/{TOKEN}/invitation').json()['opening_style']=='classic'
    response=client.patch(url,headers=admin_headers,json={'opening_style':'envelope'})
    assert response.status_code==200
    assert client.get(f'/api/events/{TOKEN}/invitation').json()['opening_style']=='envelope'
    client.patch(url,headers=admin_headers,json={'tagline':'Yeni'})
    assert client.get(f'/api/events/{TOKEN}/invitation').json()['opening_style']=='envelope'
    assert client.patch(url,headers=admin_headers,json={'opening_style':'unknown'}).status_code==422
    assert client.patch(url,headers=admin_headers,json={'opening_style':None}).status_code==422
    assert client.patch(url,json={'opening_style':'classic'}).status_code==401
    assert client.patch(url,headers=admin_headers,json={'opening_style':'classic'}).json()['opening_style']=='classic'

def test_envelope_appearance_persists_and_validates(client,admin_headers):
    url=f'/api/admin/events/{TOKEN}/invitation'
    appearance={'envelope_color':'#345678','seal_color':'#982345','paper_color':'#fffaaa','envelope_texture':'grain','envelope_pattern':'botanical','seal_motif':'monogram'}
    assert client.patch(url,headers=admin_headers,json=appearance).status_code==200
    public=client.get(f'/api/events/{TOKEN}/invitation').json()
    for key,value in appearance.items():
        assert public[key]==value
    client.patch(url,headers=admin_headers,json={'tagline':'Updated'})
    assert client.get(f'/api/events/{TOKEN}/invitation').json()['envelope_color']=='#345678'
    for invalid in [{'seal_color':'red'},{'envelope_texture':'invalid'},{'seal_motif':None},{'paper_color':'#fff;url(x)'},{'envelope_pattern':'invalid'}]:
        assert client.patch(url,headers=admin_headers,json=invalid).status_code==422

def test_reference_patterns_persist(client,admin_headers):
    url=f'/api/admin/events/{TOKEN}/invitation'
    for pattern in ('lace','floral_cut','embossed'):
        response=client.patch(url,headers=admin_headers,json={'envelope_pattern':pattern})
        assert response.status_code==200
        assert client.get(f'/api/events/{TOKEN}/invitation').json()['envelope_pattern']==pattern
