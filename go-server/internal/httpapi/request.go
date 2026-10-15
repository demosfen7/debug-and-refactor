package httpapi

import (
	"encoding/json"
	"io"
	"mime"
	"net/http"
	"strings"
)

const (
	maxBodyBytes = 1 << 20
	nameError    = "field 'name' must be a non-empty string"
)

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
