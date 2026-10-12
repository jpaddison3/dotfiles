#!/usr/bin/env python3
"""Render candidate meeting slots over guests' calendars as a Google-Calendar-style week view.

Usage: render.py SPEC.json [-o OUT.png] [--open] [--focus]

SPEC (JSON):
  title         heading, e.g. "Huon / JP post-bout"
  tz            display time zone (IANA), default America/New_York
  secondary_tz  optional second time gutter (IANA), e.g. Europe/London
  week_start    first day shown, YYYY-MM-DD
  days          number of days, default 5
  hours         [first, last] hour shown in tz, default fits options within 8am-6pm
  people        [{name, color?, busy_only?, events?: [...], gcal_json?: path}]
                  events: {title, start, end, status?} where status is one of
                  accepted (default) | needsAction | tentative | free | declined.
                  Times are ISO 8601; a time without an offset is read in tz. An
                  all-day event uses a bare date for start and end (end exclusive).
                  gcal_json: a saved Google Calendar list_events response; its
                  events are converted (declined and cancelled ones dropped).
  options       [{label, start, end, note?, recommended?}]

Writes OUT.png (default: alongside SPEC) via headless Chrome. --open shows it in
Orca when running inside Orca (copied into the worktree's git-excluded
.meeting-options/ folder, since Orca only opens worktree files), else in Preview.
"""
import argparse, html, json, math, os, shutil, subprocess, sys, tempfile
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
# Google Calendar palette: Peacock, Grape, Basil, Tangerine, Blueberry, Flamingo, Graphite.
PALETTE = ['#039be5', '#8e24aa', '#0b8043', '#f4511e', '#3f51b5', '#e67c73', '#616161']
HOUR_PX, COL_W, GUTTER_W, HEAD_H = 56, 210, 56, 150


def parse_time(s, tz):
    dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
    return (dt.replace(tzinfo=tz) if dt.tzinfo is None else dt).astimezone(tz)


def from_gcal(path):
    with open(path) as f:
        data = json.load(f)
    out = []
    for e in data.get('events', data) if isinstance(data, dict) else data:
        if e.get('status') == 'cancelled' or e.get('eventType') == 'WORKING_LOCATION':
            continue
        me = next((a for a in e.get('attendees', []) if a.get('self')), {})
        status = me.get('responseStatus', 'accepted')
        if status == 'declined':
            continue
        if e.get('transparency') == 'transparent' or e.get('availability') == 'AVAILABILITY_FREE':
            status = 'free'
        s, en = e.get('start', {}), e.get('end', {})
        out.append({'title': e.get('summary', '(No title)'), 'start': s.get('dateTime') or s.get('date')[:10],
                    'end': en.get('dateTime') or en.get('date')[:10], 'status': status, 'id': e.get('id')})
    return out


def layout(items):
    """Side-by-side columns for overlapping timed items: sets col and ncols on each."""
    items.sort(key=lambda x: (x['s'], -(x['e'] - x['s'])))
    cluster, cols, end = [], [], None

    def flush():
        for it in cluster:
            it['ncols'] = len(cols)

    for it in items:
        if end is not None and it['s'] >= end:
            flush()
            cluster, cols, end = [], [], None
        for i, c in enumerate(cols):
            if c <= it['s']:
                cols[i], it['col'] = it['e'], i
                break
        else:
            it['col'] = len(cols)
            cols.append(it['e'])
        cluster.append(it)
        end = max(end or it['e'], it['e'])
    flush()


def fmt(dt, with_ampm=True):
    h = dt.hour % 12 or 12
    s = f'{h}:{dt.minute:02d}' if dt.minute else f'{h}'
    return s + (('am' if dt.hour < 12 else 'pm') if with_ampm else '')


def span(a, b):
    same = (a.hour < 12) == (b.hour < 12)
    return f'{fmt(a, not same)}–{fmt(b)}'


def build(spec):
    tz = ZoneInfo(spec.get('tz', 'America/New_York'))
    tz2 = ZoneInfo(spec['secondary_tz']) if spec.get('secondary_tz') else None
    d0 = date.fromisoformat(spec['week_start'])
    ndays = spec.get('days', 5)
    days = [d0 + timedelta(i) for i in range(ndays)]
    opts = [dict(o, s=parse_time(o['start'], tz), e=parse_time(o['end'], tz)) for o in spec.get('options', [])]
    if spec.get('hours'):
        h0, h1 = spec['hours']
    else:
        h0 = min([8] + [o['s'].hour for o in opts])
        h1 = max([18] + [math.ceil(o['e'].hour + o['e'].minute / 60) for o in opts])

    people, timed, allday = [], {d: [] for d in days}, {d: [] for d in days}
    for i, p in enumerate(spec['people']):
        color = p.get('color') or PALETTE[i % len(PALETTE)]
        people.append({'name': p['name'], 'color': color})
        evs = list(p.get('events', []))
        if p.get('gcal_json'):
            evs += from_gcal(p['gcal_json'])
        seen = set()
        for ev in evs:
            key = ev.get('id') or (ev['title'], ev['start'], ev['end'])
            if key in seen:
                continue
            seen.add(key)
            title = 'Busy' if p.get('busy_only') else ev['title']
            status = ev.get('status', 'accepted')
            if status == 'declined':
                continue
            if len(ev['start']) == 10:
                a, b = date.fromisoformat(ev['start']), date.fromisoformat(ev['end'])
                for d in days:
                    if a <= d < b:
                        allday[d].append({'title': title, 'color': color, 'status': status})
                continue
            s, e = parse_time(ev['start'], tz), parse_time(ev['end'], tz)
            for d in days:
                lo = datetime.combine(d, datetime.min.time(), tz).replace(hour=h0)
                hi = datetime.combine(d, datetime.min.time(), tz).replace(hour=h1)
                if s < hi and e > lo:
                    timed[d].append({'title': title, 'color': color, 'status': status, 'rs': s, 're': e,
                                     's': max(s, lo), 'e': min(e, hi)})

    def y(dt):
        return (dt.hour + dt.minute / 60 - h0) * HOUR_PX

    gutters = GUTTER_W * (2 if tz2 else 1)
    ad_rows = max([len(v) for v in allday.values()] + [0])
    ad_h = ad_rows * 22 + (8 if ad_rows else 0)
    grid_top = HEAD_H + ad_h
    width = gutters + COL_W * ndays + 24
    grid_h = (h1 - h0) * HOUR_PX
    legend_h = 40 + 26 * len(opts)
    height = grid_top + grid_h + legend_h + 16

    out = []
    w = out.append
    w(f'<div class="title">{html.escape(spec.get("title", "Meeting options"))}</div>')
    w('<div class="meetwith"><span class="mw-label">Meet with…</span>')
    for p in people:
        initials = ''.join(x[0] for x in p['name'].split() if x[0].isalpha())[:2].upper()
        w(f'<span class="chip"><span class="av" style="background:{p["color"]}">{initials}</span>{html.escape(p["name"])}</span>')
    w('</div>')
    tzname = lambda z, d: datetime.combine(d, datetime.min.time(), z).replace(hour=12).strftime('%Z')
    if tz2:
        w(f'<div class="tzl" style="left:0;top:{HEAD_H - 18}px">{tzname(tz2, d0)}</div>')
    w(f'<div class="tzl" style="left:{gutters - GUTTER_W}px;top:{HEAD_H - 18}px">{tzname(tz, d0)}</div>')
    for i, d in enumerate(days):
        x = gutters + i * COL_W
        w(f'<div class="dayhead" style="left:{x}px;width:{COL_W}px"><div class="dow">{d.strftime("%a").upper()}</div>'
          f'<div class="dnum">{d.day}</div></div>')
        for j, a in enumerate(allday[d]):
            cls = 'ad free' if a['status'] in ('free', 'needsAction', 'tentative') else 'ad'
            w(f'<div class="{cls}" style="left:{x + 2}px;top:{HEAD_H + j * 22}px;width:{COL_W - 6}px;'
              f'--c:{a["color"]}">{html.escape(a["title"])}</div>')
    for h in range(h0, h1 + 1):
        top = grid_top + (h - h0) * HOUR_PX
        w(f'<div class="hline" style="top:{top}px;left:{gutters - 8}px;width:{COL_W * ndays + 8}px"></div>')
        if h == h0 or h == h1:
            continue
        t = datetime.combine(d0, datetime.min.time(), tz).replace(hour=h)
        w(f'<div class="hlab" style="top:{top - 7}px;left:{gutters - GUTTER_W}px;width:{GUTTER_W - 12}px">{fmt(t).upper()}</div>')
        if tz2:
            t2 = t.astimezone(tz2)
            w(f'<div class="hlab sec" style="top:{top - 7}px;left:0;width:{GUTTER_W - 12}px">{fmt(t2).upper()}</div>')
    for i in range(ndays + 1):
        x = gutters + i * COL_W
        w(f'<div class="vline" style="left:{x}px;top:{HEAD_H - 6}px;height:{grid_h + ad_h + 6}px"></div>')
    for i, d in enumerate(days):
        x0 = gutters + i * COL_W
        layout(timed[d])
        for ev in timed[d]:
            cw = (COL_W - 10) / ev['ncols']
            left, top = x0 + 1 + ev['col'] * cw, grid_top + y(ev['s']) + 1
            hgt = max(y(ev['e']) - y(ev['s']) - 2, 12)
            cls = {'free': 'ev free', 'needsAction': 'ev pending', 'tentative': 'ev pending'}.get(ev['status'], 'ev')
            title = html.escape(ev['title'])
            if hgt >= 30:
                lines = max(1, int((hgt - 4) // 14) - 1)
                inner = (f'<div class="t" style="-webkit-line-clamp:{lines}">{title}</div>'
                         f'<div class="one">{span(ev["rs"], ev["re"])}</div>')
                extra = ''
            else:
                inner = f'<div class="one"><b>{title}</b>, {fmt(ev["rs"])}</div>'
                extra = f'padding-top:0;padding-bottom:0;line-height:{hgt - 2:.0f}px;'
            w(f'<div class="{cls}" style="left:{left:.1f}px;top:{top:.1f}px;width:{cw - 2:.1f}px;height:{hgt:.1f}px;'
              f'{extra}--c:{ev["color"]}">{inner}</div>')
        for o in opts:
            if o['s'].date() != d:
                continue
            top, hgt = grid_top + y(o['s']), max(y(o['e']) - y(o['s']), 18)
            cls = 'opt rec' if o.get('recommended') else 'opt'
            star = ' ★' if o.get('recommended') else ''
            w(f'<div class="{cls}" style="left:{x0 + 1}px;top:{top:.1f}px;width:{COL_W - 4}px;height:{hgt:.1f}px">'
              f'<span class="olab">{html.escape(o["label"])}{star}</span> {span(o["s"], o["e"])}</div>')
    ly = grid_top + grid_h + 24
    for k, o in enumerate(opts):
        star = ' ★ recommended' if o.get('recommended') else ''
        alt = f' · {span(o["s"].astimezone(tz2), o["e"].astimezone(tz2))} {o["s"].astimezone(tz2).strftime("%Z")}' if tz2 else ''
        note = f' — {html.escape(o["note"])}' if o.get('note') else ''
        w(f'<div class="leg" style="top:{ly + k * 26}px;left:{gutters}px"><span class="olab">{html.escape(o["label"])}</span> '
          f'<b>{o["s"].strftime("%a %-m/%-d")}, {span(o["s"], o["e"])} {o["s"].strftime("%Z")}</b>{alt}{star}{note}</div>')

    css = """
*{box-sizing:border-box;margin:0}
body{background:#fff;font-family:'Google Sans','Roboto',-apple-system,'Helvetica Neue',Arial,sans-serif;color:#3c4043;
  width:%dpx;height:%dpx;position:relative;overflow:hidden}
div,span{position:absolute}
.title{left:24px;top:16px;font-size:22px;color:#202124}
.meetwith{left:24px;top:54px;display:flex;gap:8px;align-items:center;position:absolute}
.meetwith>*{position:static}
.mw-label{font-size:13px;color:#5f6368;margin-right:4px}
.chip{display:flex;align-items:center;gap:6px;border:1px solid #dadce0;border-radius:16px;padding:3px 10px 3px 3px;font-size:13px}
.chip .av,.chip>*{position:static}
.av{width:22px;height:22px;border-radius:50%%;color:#fff;font-size:10px;font-weight:600;display:flex;align-items:center;justify-content:center}
.dayhead{top:96px;text-align:center}
.dow{position:static;font-size:11px;font-weight:500;color:#70757a;letter-spacing:.8px}
.dnum{position:static;font-size:24px;color:#3c4043;line-height:32px}
.tzl{font-size:10px;color:#70757a;width:%dpx;text-align:right;padding-right:12px}
.hline{height:1px;background:#e0e0e0}
.vline{width:1px;background:#e0e0e0}
.hlab{font-size:10px;color:#70757a;text-align:right}
.hlab.sec{color:#9aa0a6}
.ev{border-radius:5px;background:var(--c);color:#fff;font-size:11px;line-height:14px;padding:2px 6px;overflow:hidden;
  border:1px solid #fff}
.ev *{position:static}
.ev b,.ev .t{font-weight:500}
.ev .t{display:-webkit-box;-webkit-box-orient:vertical;overflow:hidden}
.ev .one{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ev.pending{background:#fff;color:var(--c);border:1px solid var(--c)}
.ev.free{background:color-mix(in srgb,var(--c) 22%%,#fff);color:#3c4043;border:1px solid #fff}
.ad{height:20px;border-radius:4px;background:var(--c);color:#fff;font-size:11px;line-height:20px;padding:0 6px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ad.free{background:color-mix(in srgb,var(--c) 22%%,#fff);color:#3c4043}
.opt{border:2px dashed #188038;background:rgba(24,128,56,.14);border-radius:6px;z-index:5;font-size:11px;color:#0d652d;
  padding:1px 5px;font-weight:500;white-space:nowrap;overflow:hidden}
.opt.rec{border-style:solid;background:rgba(24,128,56,.22);box-shadow:0 2px 6px rgba(0,0,0,.25)}
.olab{position:static;display:inline-block;background:#188038;color:#fff;border-radius:4px;padding:0 5px;font-weight:600}
.leg{font-size:13px;white-space:nowrap}
""" % (width, height, GUTTER_W)
    doc = f'<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{"".join(out)}</body></html>'
    return doc, width, height


def render(doc, width, height, out_png):
    with tempfile.TemporaryDirectory() as td:
        page = os.path.join(td, 'page.html')
        with open(page, 'w') as f:
            f.write(doc)
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
                        f'--window-size={width},{height}', f'--screenshot={os.path.abspath(out_png)}', f'file://{page}'],
                       check=True, capture_output=True)


def show(png, focus):
    if os.environ.get('ORCA_WORKTREE_ID'):
        top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True).stdout.strip()
        if top:
            dest_dir = os.path.join(top, '.meeting-options')
            os.makedirs(dest_dir, exist_ok=True)
            exclude = subprocess.run(['git', 'rev-parse', '--git-path', 'info/exclude'], cwd=top,
                                     capture_output=True, text=True).stdout.strip()
            exclude = os.path.join(top, exclude) if exclude and not os.path.isabs(exclude) else exclude
            if exclude:
                existing = open(exclude).read() if os.path.exists(exclude) else ''
                if '.meeting-options/' not in existing.split('\n'):
                    with open(exclude, 'a') as f:
                        f.write(('' if existing.endswith('\n') or not existing else '\n') + '.meeting-options/\n')
            dest = os.path.join(dest_dir, os.path.basename(png))
            if os.path.abspath(png) != dest:
                shutil.copyfile(png, dest)
            subprocess.run(['orca', 'file', 'open', dest] + (['--focus'] if focus else []), check=True)
            return dest
    subprocess.run(['open', '-a', 'Preview', png], check=True)
    return png


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('spec')
    ap.add_argument('-o', '--out')
    ap.add_argument('--open', action='store_true', help='show the image in Orca (or Preview outside Orca)')
    ap.add_argument('--focus', action='store_true', help='with --open in Orca, switch the view to the image')
    a = ap.parse_args()
    with open(a.spec) as f:
        spec = json.load(f)
    out = a.out or os.path.splitext(a.spec)[0] + '.png'
    doc, width, height = build(spec)
    render(doc, width, height, out)
    print(out)
    if a.open:
        print('opened:', show(out, a.focus))


if __name__ == '__main__':
    sys.exit(main())
