package main

import (
	"strings"
)

// Built-in RBAC roles for API keys.
const RoleChatOnly = "chat_only"

const ctxKeyAPIRoles = "api_roles"

func normalizeRoles(in []string) []string {
	if len(in) == 0 {
		return nil
	}
	seen := make(map[string]struct{}, len(in))
	var out []string
	for _, raw := range in {
		r := normalizeRoleName(raw)
		if r == "" {
			continue
		}
		if _, ok := seen[r]; ok {
			continue
		}
		seen[r] = struct{}{}
		out = append(out, r)
	}
	return out
}

func normalizeRoleName(raw string) string {
	switch strings.ToLower(strings.TrimSpace(raw)) {
	case RoleChatOnly, "chat", "chat-only":
		return RoleChatOnly
	default:
		return ""
	}
}

func defaultAPIKeyRoles() []string {
	return []string{RoleChatOnly}
}

func canUseChatAPI(apiRoles []string) bool {
	for _, r := range apiRoles {
		if r == RoleChatOnly {
			return true
		}
	}
	return false
}
