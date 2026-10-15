package httpapi

import (
	"errors"
	"log"
	"net/http"
	"strconv"

	"github.com/demosfen7/debug-and-refactor/go-server/internal/model"
)

func addUserHandler(users UserStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		name, ok := parseName(w, r)
		if !ok {
			writeError(w, http.StatusBadRequest, nameError)
			return
		}

		u, err := users.AddUser(r.Context(), name)
		if err != nil {
			log.Printf("add user: %v", err)
			writeError(w, http.StatusInternalServerError, "internal error")
			return
		}
		w.Header().Set("Location", "/user/"+strconv.FormatInt(u.ID, 10))
		writeJSON(w, http.StatusCreated, u)
	}
}

func getUserHandler(users UserStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Как <int:uid> во Flask: нечисловой id — это несуществующий ресурс.
		id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
		if err != nil {
			writeError(w, http.StatusNotFound, "user not found")
			return
		}

		u, err := users.GetUser(r.Context(), id)
		if errors.Is(err, model.ErrNotFound) {
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
