// Package store — хранилище пользователей в SQLite.
package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"

	_ "modernc.org/sqlite" // драйвер SQLite на чистом Go, cgo не нужен

	"github.com/demosfen7/debug-and-refactor/go-server/internal/model"
)

const schema = `
CREATE TABLE IF NOT EXISTS users (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)`

// Применяются к каждому соединению пула. busy_timeout стоит первым, чтобы
// остальные прагмы тоже ждали блокировку, а не падали с "database is locked".
// WAL + synchronous=NORMAL — та же настройка, что в Python-версии: без неё
// параллельные писатели не укладываются в таймаут.
const pragmas = "?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)&_pragma=synchronous(NORMAL)"

type Store struct {
	db *sql.DB
}

// Open открывает (или создаёт) файл БД и таблицу users.
func Open(path string) (*Store, error) {
	db, err := sql.Open("sqlite", path+pragmas)
	if err != nil {
		return nil, fmt.Errorf("open %s: %w", path, err)
	}
	if _, err := db.Exec(schema); err != nil {
		db.Close()
		return nil, fmt.Errorf("init schema in %s: %w", path, err)
	}
	return &Store{db: db}, nil
}

func (s *Store) Close() error {
	return s.db.Close()
}

func (s *Store) AddUser(ctx context.Context, name string) (model.User, error) {
	res, err := s.db.ExecContext(ctx, "INSERT INTO users (name) VALUES (?)", name)
	if err != nil {
		return model.User{}, fmt.Errorf("insert user: %w", err)
	}
	id, err := res.LastInsertId()
	if err != nil {
		return model.User{}, fmt.Errorf("insert user: %w", err)
	}
	return model.User{ID: id, Name: name}, nil
}

// GetUser возвращает model.ErrNotFound, если пользователя нет.
func (s *Store) GetUser(ctx context.Context, id int64) (model.User, error) {
	var u model.User
	err := s.db.QueryRowContext(ctx, "SELECT id, name FROM users WHERE id = ?", id).
		Scan(&u.ID, &u.Name)
	if errors.Is(err, sql.ErrNoRows) {
		return model.User{}, model.ErrNotFound
	}
	if err != nil {
		return model.User{}, fmt.Errorf("select user %d: %w", id, err)
	}
	return u, nil
}
