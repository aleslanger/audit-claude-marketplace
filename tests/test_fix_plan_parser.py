import scripts.fix_plan_parser as parser


def test_parse_md():
    issues = parser.parse_fix_plan_md('tests/fixtures/sample_FIX_PLAN.md')
    assert len(issues) == 2
    ids = [i['id'] for i in issues]
    assert 'ISSUE-001' in ids
    assert 'ISSUE-002' in ids
    first = issues[0]
    assert first['severity'] == 'CRITICAL'
    assert first['file'] == 'app/query.py:42'


def test_write_and_parse_json(tmp_path):
    md = 'tests/fixtures/sample_FIX_PLAN.md'
    out = tmp_path / 'out.json'
    parser.write_fix_plan_json(md, str(out))
    data = parser.parse_fix_plan_json(str(out))
    assert isinstance(data, list)
    assert data[0]['id'] == 'ISSUE-001'
