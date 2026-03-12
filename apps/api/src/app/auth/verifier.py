"""JWT 驗證與 principal 解析元件。"""

from dataclasses import dataclass

import jwt
from jwt import InvalidTokenError as JwtLibraryInvalidTokenError
from jwt import PyJWKClient

from app.core.settings import AppSettings


# 測試模式 token 的固定前綴，用來避免誤把一般字串當成 token。
TEST_TOKEN_PREFIX = "test::"


class InvalidTokenError(ValueError):
    """代表 token 無法通過驗證或缺少必要 claims。"""


@dataclass(frozen=True, slots=True)
class CurrentPrincipal:
    """已驗證使用者的最小 auth context。"""

    sub: str
    groups: tuple[str, ...]
    authenticated: bool = True


class TokenVerifier:
    """Token verifier 介面。"""

    def verify(self, token: str) -> CurrentPrincipal:
        """驗證 token 並回傳 principal。

        參數：
        - `token`：待驗證的 access token。

        回傳：
        - `CurrentPrincipal`：從 token 解析出的已驗證使用者資訊。
        """

        raise NotImplementedError


class KeycloakJwtVerifier(TokenVerifier):
    """使用 Keycloak JWKS 驗證 access token 的 verifier。"""

    def __init__(self, settings: AppSettings) -> None:
        """初始化 Keycloak JWT verifier。

        參數：
        - `settings`：包含 JWKS URL、issuer 與 groups claim 名稱的應用程式設定。

        回傳：
        - `None`：此建構子只負責初始化 verifier 狀態。
        """

        self._jwks_client = PyJWKClient(settings.keycloak_jwks_url)
        self._issuer = settings.keycloak_issuer
        self._groups_claim = settings.keycloak_groups_claim

    def verify(self, token: str) -> CurrentPrincipal:
        """驗證 Keycloak JWT 並解析 principal。

        參數：
        - `token`：待驗證的 Keycloak access token。

        回傳：
        - `CurrentPrincipal`：由合法 JWT 解析出的 principal。

        前置條件：
        - token 必須由設定中的 Keycloak issuer 簽發。

        風險：
        - 目前未驗證 audience，因為 API client 尚未在本專案固定；後續若引入專用 client，需同步收緊。
        """

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "RS384", "RS512"],
                issuer=self._issuer,
                options={"verify_aud": False},
            )
        except JwtLibraryInvalidTokenError as exc:
            raise InvalidTokenError("Token 驗證失敗。") from exc
        return _build_principal_from_payload(payload=payload, groups_claim=self._groups_claim)


class TestModeTokenVerifier(TokenVerifier):
    """本機測試模式使用的 verifier。

    token 格式：
    - `test::<sub>::<group1,group2>`
    - groups 可省略，表示空集合
    """

    def __init__(self, groups_claim: str) -> None:
        """初始化測試模式 verifier。

        參數：
        - `groups_claim`：測試 token 中用來對應群組列表的 claim 名稱。

        回傳：
        - `None`：此建構子只負責初始化 verifier 狀態。
        """

        self._groups_claim = groups_claim

    def verify(self, token: str) -> CurrentPrincipal:
        """解析測試模式 token。

        參數：
        - `token`：符合 `test::<sub>::<groups>` 格式的測試 token。

        回傳：
        - `CurrentPrincipal`：由測試 token 解析出的 principal。
        """

        if not token.startswith(TEST_TOKEN_PREFIX):
            raise InvalidTokenError("測試模式 token 前綴不正確。")
        try:
            _, sub, raw_groups = token.split("::", maxsplit=2)
        except ValueError as exc:
            raise InvalidTokenError("測試模式 token 格式不正確。") from exc
        payload = {
            "sub": sub,
            self._groups_claim: [group for group in raw_groups.split(",") if group],
        }
        return _build_principal_from_payload(payload=payload, groups_claim=self._groups_claim)


def _build_principal_from_payload(payload: dict[str, object], groups_claim: str) -> CurrentPrincipal:
    """從已驗證 payload 建立 principal。

    參數：
    - `payload`：已完成驗證的 JWT payload。
    - `groups_claim`：應從 payload 讀取群組列表的 claim 名稱。

    回傳：
    - `CurrentPrincipal`：由 payload 建立出的 principal。
    """

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidTokenError("Token 缺少合法的 sub claim。")

    raw_groups = payload.get(groups_claim, [])
    if raw_groups is None:
        raw_groups = []
    if not isinstance(raw_groups, list) or any(not isinstance(item, str) for item in raw_groups):
        raise InvalidTokenError("Token 的 groups claim 格式不正確。")

    return CurrentPrincipal(sub=subject, groups=tuple(raw_groups))


def build_token_verifier(settings: AppSettings) -> TokenVerifier:
    """根據設定建立 token verifier。

    參數：
    - `settings`：包含 auth mode、issuer 與 groups claim 設定的應用程式設定。

    回傳：
    - `TokenVerifier`：符合目前執行模式的 token 驗證器。
    """

    if settings.auth_test_mode:
        return TestModeTokenVerifier(groups_claim=settings.keycloak_groups_claim)
    return KeycloakJwtVerifier(settings=settings)
