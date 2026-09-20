"""Download arXiv PDFs and extract text, so claims can be checked against the
paper rather than against a search summary."""
import os, re, sys, time, urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_papers")
IDS = ["2604.11581", "2510.03992", "2609.16599", "2507.20150",
       "2209.06691", "2605.00741", "2601.18753", "2605.29816"]

os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (research; contact via arXiv)"}


def grab(aid):
    pdf = os.path.join(OUT, aid + ".pdf")
    txt = os.path.join(OUT, aid + ".txt")
    if os.path.exists(txt) and os.path.getsize(txt) > 2000:
        return aid, "cached", os.path.getsize(txt)
    if not os.path.exists(pdf) or os.path.getsize(pdf) < 10000:
        req = urllib.request.Request("https://arxiv.org/pdf/" + aid, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
        except Exception as e:
            return aid, "PDF FAIL: " + str(e)[:70], 0
        if not data.startswith(b"%PDF"):
            return aid, "not a PDF (%d bytes)" % len(data), 0
        open(pdf, "wb").write(data)
    try:
        import pypdf
        rd = pypdf.PdfReader(pdf)
        t = "\n".join(p.extract_text() or "" for p in rd.pages)
    except Exception as e:
        return aid, "EXTRACT FAIL: " + str(e)[:70], 0
    t = re.sub(r"[ \t]+", " ", t)
    open(txt, "w", encoding="utf-8").write(t)
    return aid, "ok (%d pages)" % len(rd.pages), len(t)


for aid in IDS:
    a, status, n = grab(aid)
    print("%-12s %-26s %s chars" % (a, status, n))
    sys.stdout.flush()
    time.sleep(2)
