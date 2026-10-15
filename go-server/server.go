package main

import (
	"encoding/json"
	"errors"
	"io"
	"log"
	"mime"
	"net/http"
	"strconv"
	"strings"
)

const maxBodyBytes = 1 << 20

// NewServer собирает маршруты API. Контракт совпадает с api.py.
func NewServer(store *Store) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /adduser", addUserHandler(store))
	mux.HandleFunc("GET /user/{id}", getUserHandler(store))
	return mux
}

func addUserHandler(store *Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		name, ok := parseName(w, r)
		if !ok {
			writeError(w, http.StatusBadRequest, "field 'name' must be a non-empty string")
			return
		}

		u, err := store.AddUser(r.Context(), name)
		if err != nil {
			log.Printf("add user: %v", err)
			writeError(w, http.StatusInternalServerError, "internal error")
			return
		}
		w.Header().Set("Location", "/user/"+strconv.FormatInt(u.ID, 10))
		writeJSON(w, http.StatusCreated, u)
	}
}

func getUserHandler(store *Store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Как <int:uid> во Flask: нечисловой id — это несуществующий ресурс.
		id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
		if err != nil {
			writeError(w, http.StatusNotFound, "user not found")
			return
		}

		u, err := store.GetUser(r.Context(), id)
		if errors.Is(err, ErrNotFound) {
			writeError(w, http.StatusNotFound, "user not found")
			return
		}
		if err != nil {
			log.Printf("get user: %v", err)
			writeError(w, http.StatusInternalServerError, "internal error")
			return
		}
		writeJSON(w, http.StatusOK, u)
	}
}

// parseName достаёт непустое строковое поле name из JSON-тела.
// Как request.get_json(silent=True) во Flask: тело без JSON Content-Type
// считается отсутствующим.
func parseName(w http.ResponseWriter, r *http.Request) (string, bool) {
	mediaType, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || (mediaType != "application/json" && !strings.HasSuffix(mediaType, "+json")) {
		return "", false
	}

	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, maxBodyBytes))
	if err != nil {
		return "", false
	}

	// Указатель отличает отсутствующее поле и null от пустой строки;
	// не-объект и не-строковый name дают ошибку разбора.
	var payload struct {
		Name *string `json:"name"`
	}
	if err := json.Unmarshal(body, &payload); err != nil || payload.Name == nil {
		return "", false
	}
	if strings.TrimSpace(*payload.Name) == "" {
		return "", false
	}
	return *payload.Name, true
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("write response: %v", err)
	}
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}
