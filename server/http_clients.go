package main

import (
	"net"
	"net/http"
	"time"
)

// Общий Transport для исходящих HTTP к Python и LLM (keep-alive, пул соединений).
var outboundTransport = &http.Transport{
	Proxy: http.ProxyFromEnvironment,
	DialContext: (&net.Dialer{
		Timeout:   30 * time.Second,
		KeepAlive: 30 * time.Second,
	}).DialContext,
	MaxIdleConns:        32,
	MaxIdleConnsPerHost: 8,
	IdleConnTimeout:     90 * time.Second,
}

var pythonHTTPClient = &http.Client{
	Timeout:   120 * time.Second,
	Transport: outboundTransport,
}

var classifierHTTPClient = &http.Client{
	Timeout:   30 * time.Second,
	Transport: outboundTransport,
}
