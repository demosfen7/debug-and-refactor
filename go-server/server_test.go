package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"testing"
)

func newTestServer(t *testing.T) http.Handler {
	t.Helper()
	store, err := OpenStore(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatal(err)
	}
	// Cleanup выполняется в обратном порядке: БД закроется до удаления TempDir.
	t.Cleanup(func() { store.Close() })
	return NewServer(store)
}

func do(h http.Handler, method, path, contentType, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func postUser(h http.Handler, name string) *httptest.ResponseRecorder {
	body, _ := json.Marshal(map[string]string{"name": name})
	return do(h, http.MethodPost, "/adduser", "application/json", string(body))
}

func decodeUser(t *testing.T, rec *httptest.ResponseRecorder) User {
	t.Helper()
	var u User
	if err := json.Unmarshal(rec.Body.Bytes(), &u); err != nil {
		t.Fatalf("decode %q: %v", rec.Body.String(), err)
	}
	return u
}

func decodeError(t *testing.T, rec *httptest.ResponseRecorder) string {
	t.Helper()
	var e struct {
		Error string `json:"error"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &e); err != nil {
		t.Fatalf("decode %q: %v", rec.Body.String(), err)
	}
	return e.Error
}

func TestAddUserReturns201WithIDAndLocation(t *testing.T) {
	h := newTestServer(t)
	rec := postUser(h, "alice")

	if rec.Code != http.StatusCreated {
		t.Fatalf("status = %d, want 201", rec.Code)
	}
	if got := decodeUser(t, rec); got != (User{ID: 1, Name: "alice"}) {
		t.Errorf("body = %+v", got)
	}
	if loc := rec.Header().Get("Location"); loc != "/user/1" {
		t.Errorf("Location = %q, want /user/1", loc)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q", ct)
	}
}

func TestGetUserReturns200(t *testing.T) {
	h := newTestServer(t)
	postUser(h, "alice")
	rec := do(h, http.MethodGet, "/user/1", "", "")

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	if got := decodeUser(t, rec); got != (User{ID: 1, Name: "alice"}) {
		t.Errorf("body = %+v", got)
	}
}

func TestGetMissingUserReturns404(t *testing.T) {
	h := newTestServer(t)
	rec := do(h, http.MethodGet, "/user/999", "", "")

	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", rec.Code)
	}
	if msg := decodeError(t, rec); msg != "user not found" {
		t.Errorf("error = %q", msg)
	}
}

func TestGetUserRejectsNonIntegerID(t *testing.T) {
	h := newTestServer(t)
	postUser(h, "alice")

	for _, path := range []string{"/user/abc", "/user/0%20OR%201=1", "/user/0%20UNION%20SELECT%201,2"} {
		if rec := do(h, http.MethodGet, path, "", ""); rec.Code != http.StatusNotFound {
			t.Errorf("GET %s: status = %d, want 404", path, rec.Code)
		}
	}
}

func TestAddUserRejectsBadPayload(t *testing.T) {
	cases := []struct {
		name, contentType, body string
	}{
		{"form body", "application/x-www-form-urlencoded", "name=bob"},
		{"json without content type", "text/plain", `{"name":"bob"}`},
		{"empty body", "application/json", ""},
		{"null", "application/json", "null"},
		{"array", "application/json", `["bob"]`},
		{"no name", "application/json", "{}"},
		{"null name", "application/json", `{"name":null}`},
		{"empty name", "application/json", `{"name":""}`},
		{"blank name", "application/json", `{"name":"   "}`},
		{"number name", "application/json", `{"name":42}`},
		{"broken json", "application/json", `{"name":`},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			h := newTestServer(t)
			rec := do(h, http.MethodPost, "/adduser", tc.contentType, tc.body)
			if rec.Code != http.StatusBadRequest {
				t.Fatalf("status = %d, want 400", rec.Code)
			}
			if decodeError(t, rec) == "" {
				t.Error("empty error message")
			}
		})
	}
}

func TestNamesWithQuotesAreStoredVerbatim(t *testing.T) {
	for _, name := range []string{"O'Brien", "x'),('pwned", "'; DROP TABLE users; --"} {
		t.Run(name, func(t *testing.T) {
			h := newTestServer(t)
			rec := postUser(h, name)
			if rec.Code != http.StatusCreated {
				t.Fatalf("status = %d, want 201", rec.Code)
			}
			id := decodeUser(t, rec).ID

			got := decodeUser(t, do(h, http.MethodGet, fmt.Sprintf("/user/%d", id), "", ""))
			if got.Name != name {
				t.Errorf("name = %q, want %q", got.Name, name)
			}
			// инъекция не создала лишних строк
			if rec := do(h, http.MethodGet, "/user/2", "", ""); rec.Code != http.StatusNotFound {
				t.Errorf("GET /user/2: status = %d, want 404", rec.Code)
			}
		})
	}
}

func TestAddUserOnlyAcceptsPost(t *testing.T) {
	h := newTestServer(t)
	if rec := do(h, http.MethodGet, "/adduser", "", ""); rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("status = %d, want 405", rec.Code)
	}
}

func TestConcurrentRequests(t *testing.T) {
	h := newTestServer(t)

	const workers, perWorker = 20, 10
	var (
		mu     sync.Mutex
		ids    []int64
		failures []string
		wg     sync.WaitGroup
	)
	for n := 0; n < workers; n++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			for i := 0; i < perWorker; i++ {
				rec := postUser(h, fmt.Sprintf("u%d-%d", n, i))
				mu.Lock()
				if rec.Code == http.StatusCreated {
					var u User
					_ = json.Unmarshal(rec.Body.Bytes(), &u)
					ids = append(ids, u.ID)
				} else {
					failures = append(failures, fmt.Sprintf("%d %s", rec.Code, rec.Body.String()))
				}
				mu.Unlock()
			}
		}(n)
	}
	wg.Wait()

	if len(failures) > 0 {
		t.Fatalf("%d failed requests, first: %s", len(failures), failures[0])
	}
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	for i, id := range ids {
		if id != int64(i+1) {
			t.Fatalf("ids are not 1..%d: got %d at position %d", workers*perWorker, id, i)
		}
	}
	if len(ids) != workers*perWorker {
		t.Fatalf("got %d ids, want %d", len(ids), workers*perWorker)
	}
}
