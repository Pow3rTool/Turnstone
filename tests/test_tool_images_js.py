"""Opt-in, same-origin tool image disclosure (shared by both chat surfaces)."""

from pathlib import Path

from tests._js_harness_helpers import FAKE_DOM, run_node_source

ROOT = Path(__file__).resolve().parents[1]


def test_images_are_lazy_scoped_and_retryable():
    module = ROOT / "turnstone/shared_static/composer_attachments.js"
    script = (
        FAKE_DOM
        + f"""
const {{ buildToolImages }} = await import({str(module.as_uri())!r});
const create = document.createElement;
document.createElement = (tag) => {{ const el = create(tag); el.style = {{}}; return el; }};
const images = [{{kind: 'image', attachment_id: 'id/1', filename: '<img onerror=bad>'}}];
const opts = {{wsId: 'ws/2', base: '/node/lab'}};
const view = buildToolImages(images, opts);
if (view.open || view.tagName !== 'DETAILS') throw Error('must start collapsed');
if (view.children[1].children.length) throw Error('must not load pixels until opened');
view.open = true;
view.dispatch('toggle');
const link = view.children[1].children[0];
const img = link.children[0];
if (img.src !== '/node/lab/v1/api/workstreams/ws%2F2/attachments/id%2F1/content') throw Error('wrong scope');
if (img.alt !== images[0].filename || link.rel !== 'noopener noreferrer') throw Error('unsafe metadata');
img.dispatch('error');
if (!link.textContent.includes('reopen')) throw Error('missing retry explanation');
view.open = false;
view.dispatch('toggle');
view.open = true;
view.dispatch('toggle');
if (view.children[1].children.length !== 1 || view.children[1].children[0] === link) throw Error('retry must replace');
if (buildToolImages([], opts) !== null) throw Error('empty');
if (buildToolImages([{{kind:'image', url:'https://evil.test/image'}}], opts) !== null) throw Error('remote URL');
if (buildToolImages(images, {{wsId:''}}) !== null) throw Error('missing scope');
"""
    )
    result = run_node_source(script)
    assert result.returncode == 0, result.stderr


def test_live_and_history_surfaces_pass_attachment_metadata():
    interactive = (ROOT / "turnstone/shared_static/interactive.js").read_text()
    coordinator = (ROOT / "turnstone/console/static/coordinator/coordinator.js").read_text()
    assert "attachments: evt.attachments" in interactive
    assert "buildToolImages(msg.attachments" in interactive
    assert "buildToolImages(opts.attachments" in interactive
    assert "attachments: ev.attachments" in coordinator
    assert "attachments: m.attachments" in coordinator
    assert "buildToolImages(opts && opts.attachments" in coordinator
