// Package model описывает данные, которыми оперирует API.
package model

import "errors"

// ErrNotFound возвращается хранилищем, когда пользователя с таким id нет.
var ErrNotFound = errors.New("user not found")

// User — пользователь HTTP API.
type User struct {
	ID   int64  `json:"id"`
	Name string `json:"name"`
}
