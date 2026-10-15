// Package httpapi — HTTP-слой: маршруты, разбор запросов, JSON-ответы.
// Контракт совпадает с Python-версией.
package httpapi

import (
	"context"
	"net/http"

	"github.com/demosfen7/debug-and-refactor/go-server/internal/model"
)

// UserStore — то, что HTTP-слою нужно от хранилища. GetUser должен
// возвращать model.ErrNotFound, если пользователя нет.
type UserStore interface {
	AddUser(ctx context.Context, name string) (model.User, error)
	GetUser(ctx context.Context, id int64) (model.User, error)
}

// NewServer собирает маршруты API.
func NewServer(users UserStore) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /adduser", addUserHandler(users))
	mux.HandleFunc("GET /user/{id}", getUserHandler(users))
	return mux
}
