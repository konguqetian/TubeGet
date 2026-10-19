"""网络层：显式 CA 证书、代理支持、带进度的下载。

为什么需要这一层
----------------
PyInstaller 打包后会带入构建机上的 OpenSSL，其默认证书路径是**构建机**的路径
（macOS 上形如 /Library/Frameworks/Python.framework/Versions/3.12/etc/openssl/cert.pem），
在用户机器上并不存在。于是 ``ssl.create_default_context()`` 找不到任何根证书，
所有 HTTPS 请求都以 ``CERTIFICATE_VERIFY_FAILED`` 失败——包括下载引擎本身。

这里显式携带一份 certifi 证书包，并在「自动兼容」模式下把系统信任库
（macOS 钥匙串 / Windows 根证书存储）合并进来，从而覆盖本地代理软件
（Clash、Surge 等）安装的自签 CA。
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from platform_paths import bundle_dir, user_data_dir

# 证书校验模式（与 UI 下拉框对应）
SSL_MODES = (
    ("strict", "严格校验"),
    ("compat", "自动兼容（推荐）"),
    ("off", "关闭校验（不安全）"),
)

# spec 的 datas 会把 cacert.pem 放到 <_MEIPASS>/certifi/ 下
_BUNDLED_CA_REL = Path("certifi") / "cacert.pem"
_SYS_CA_TTL = 7 * 86400  # 系统证书缓存有效期


class NetworkError(RuntimeError):
    """带排查提示的网络错误。"""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


# ---------------------------------------------------------------- CA 证书
def bundled_ca_bundle() -> Path | None:
    """随包分发的 certifi 根证书（优先 import，其次按相对路径找）。"""
    try:
        import certifi  # noqa: PLC0415

        p = Path(certifi.where())
        if p.is_file():
            return p
    except Exception:
        pass
    for base in (bundle_dir(), Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "_MEIPASS", None) else None):
        if not base:
            continue
        cand = base / _BUNDLED_CA_REL
        if cand.is_file():
            return cand
    return None


def _collect_system_certs() -> list[str]:
    """从操作系统信任库导出 PEM 证书列表。"""
    out: list[str] = []

    if sys.platform == "darwin":
        # 1) macOS 系统信任库（/private/etc/ssl/cert.pem 由 Security 框架维护，
        #    含全部系统根证书；这是打包应用最可靠的系统证书来源）
        for p in ("/private/etc/ssl/cert.pem", "/etc/ssl/cert.pem"):
            f = Path(p)
            if f.is_file():
                try:
                    out.append(f.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    pass
                break
        # 2) 钥匙串里用户/管理员自行安装的证书（本地代理软件的自签 CA 多在这里）
        keychains = [
            Path("/Library/Keychains/System.keychain"),
            Path.home() / "Library" / "Keychains" / "login.keychain",
        ]
        existing = [str(k) for k in keychains if k.is_file()]
        if existing:
            try:
                r = subprocess.run(
                    ["security", "find-certificate", "-a", "-p", *existing],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if r.returncode == 0 and "BEGIN CERTIFICATE" in r.stdout:
                    out.append(r.stdout)
            except Exception:
                pass

    elif os.name == "nt":
        for store in ("ROOT", "CA"):
            try:
                for der, _trust in ssl.enum_certificates(store):  # type: ignore[attr-defined]
                    b64 = base64.b64encode(der).decode("ascii")
                    out.append(
                        "-----BEGIN CERTIFICATE-----\n" + b64 + "\n-----END CERTIFICATE-----\n"
                    )
            except Exception:
                continue

    else:
        for p in (
            "/etc/ssl/certs/ca-certificates.crt",
            "/etc/pki/tls/certs/ca-bundle.crt",
            "/etc/ssl/cert.pem",
        ):
            f = Path(p)
            if f.is_file():
                try:
                    out.append(f.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    pass
                break

    return [t for t in out if "BEGIN CERTIFICATE" in t]


def system_ca_bundle() -> Path | None:
    """系统信任库导出结果（带 7 天缓存，写不进去也不影响使用）。"""
    try:
        cached = user_data_dir() / "cacert-system.pem"
        if (
            cached.is_file()
            and cached.stat().st_size > 0
            and time.time() - cached.stat().st_mtime < _SYS_CA_TTL
        ):
            return cached
    except Exception:
        return None

    certs = _collect_system_certs()
    if not certs:
        return None
    try:
        target = user_data_dir() / "cacert-system.pem"
        target.write_text("\n".join(certs), encoding="utf-8")
        return target
    except Exception:
        return None


def effective_ca_bundle(ssl_mode: str = "compat") -> Path | None:
    """当前模式实际使用的 CA 证书文件。"""
    base = bundled_ca_bundle()
    if ssl_mode != "compat" or base is None:
        return base
    sys_pem = system_ca_bundle()
    if sys_pem is None:
        return base
    try:
        merged = user_data_dir() / "cacert-merged.pem"
        text = base.read_text(encoding="utf-8") + "\n" + sys_pem.read_text(encoding="utf-8")
        if not merged.is_file() or merged.read_text(encoding="utf-8") != text:
            merged.write_text(text, encoding="utf-8")
        return merged
    except Exception:
        return base


def ca_bundle_info(ssl_mode: str = "compat") -> dict:
    """诊断信息：当前 CA 来源与规模。"""
    eff = effective_ca_bundle(ssl_mode)
    info = {
        "bundled": str(bundled_ca_bundle() or ""),
        "system": str(system_ca_bundle() or ""),
        "effective": str(eff or ""),
        "cert_count": 0,
    }
    if eff and eff.is_file():
        try:
            info["cert_count"] = eff.read_text(encoding="utf-8", errors="ignore").count(
                "BEGIN CERTIFICATE"
            )
        except Exception:
            pass
    return info


# ---------------------------------------------------------------- 上下文
def make_context(ssl_mode: str = "compat") -> ssl.SSLContext:
    """按模式构造 SSL 上下文；证书加载失败时退回系统默认（不抛异常）。"""
    if ssl_mode == "off":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    ctx = ssl.create_default_context()
    ca = effective_ca_bundle(ssl_mode)
    if ca:
        try:
            ctx.load_verify_locations(cafile=str(ca))
        except Exception:
            pass
    return ctx


# ---------------------------------------------------------------- 请求
def _opener(proxy: str | None, ssl_mode: str | None = None) -> urllib.request.OpenerDirector:
    """构造 opener；https 且指定了证书模式时挂上自定义 HTTPSHandler。"""
    handlers: list = []
    p = (proxy or "").strip()
    if p:
        handlers.append(urllib.request.ProxyHandler({"http": p, "https": p}))
    if ssl_mode:
        handlers.append(urllib.request.HTTPSHandler(context=make_context(ssl_mode)))
    return urllib.request.build_opener(*handlers)


def detected_proxy() -> str:
    """当前生效的代理（环境变量或 macOS 系统设置）。"""
    for k in ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY"):
        v = os.environ.get(k)
        if v:
            return v
    try:
        probes = urllib.request.getproxies()
        for k in ("https", "http"):
            if probes.get(k):
                return probes[k]
    except Exception:
        pass
    return ""


def _wrap_error(e: Exception, url: str) -> NetworkError:
    reason = getattr(e, "reason", None)
    text = str(reason or e)
    hint = "请检查网络连接；如在代理环境下，可在「高级选项 → 代理」填写代理地址。"
    if isinstance(reason, ssl.SSLError) or "CERTIFICATE" in text.upper():
        hint = (
            "TLS 证书校验失败。常见原因：\n"
            "1. 本地代理软件（Clash/Surge 等）接管了流量并替换证书 → "
            "在「应用 → 更新与网络设置 → 证书校验」选择「自动兼容」；\n"
            "2. 系统时间不正确 → 校正系统时钟；\n"
            "3. 仍不行可临时选「关闭校验（不安全）」。"
        )
    elif isinstance(reason, ConnectionResetError) or "timed out" in text.lower():
        hint = "连接被重置或超时。如在代理环境下，请填写代理地址后重试。"
    return NetworkError(f"请求失败：{url}\n{text}", hint)


def open_url(
    url: str,
    *,
    timeout: int = 30,
    headers: dict | None = None,
    proxy: str | None = None,
    ssl_mode: str = "compat",
):
    """带显式 CA 与代理的 urlopen 替代。"""
    hdrs = {"User-Agent": "TubeGet"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, headers=hdrs)
    opener = _opener(proxy, ssl_mode if url.lower().startswith("https") else None)
    try:
        return opener.open(req, timeout=timeout)
    except urllib.error.URLError as e:
        raise _wrap_error(e, url) from e
    except Exception as e:  # noqa: BLE001
        raise _wrap_error(e, url) from e


def get_json(url: str, *, timeout: int = 30, headers: dict | None = None,
             proxy: str | None = None, ssl_mode: str = "compat") -> dict:
    hdrs = {"Accept": "application/vnd.github+json"}
    hdrs.update(headers or {})
    with open_url(url, timeout=timeout, headers=hdrs, proxy=proxy, ssl_mode=ssl_mode) as r:
        return json.loads(r.read().decode("utf-8"))


def download(
    url: str,
    dest: Path,
    *,
    progress=None,
    timeout: int = 120,
    headers: dict | None = None,
    proxy: str | None = None,
    ssl_mode: str = "compat",
) -> Path:
    """流式下载，progress(done, total)。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open_url(url, timeout=timeout, headers=headers, proxy=proxy, ssl_mode=ssl_mode) as r, \
            open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if total and dest.stat().st_size != total:
        dest.unlink(missing_ok=True)
        raise NetworkError(f"下载文件不完整（{dest.stat().st_size}/{total} 字节），已丢弃")
    return dest
