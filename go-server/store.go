package main

import (
	"context"
	"database/sql"
	"errors"
	"fmt"

	_ "modernc.org/sqlite" // драйвер SQLite на чистом Go, cgo не нужен
)

const schema = `
CREATE TABLE IF NOT EXISTS users (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)`

// Применяются к каждому соединению пула. busy_timeout стоит первым, чтобы
// остальные прагмы тоже ждали блокировку, а не падали с "database is locked".
// WAL + synchronous=NORMAL — та же настройка, что в api.py: без неё параллельные
// писатели не укладываются в таймаут.
const pragmas = "?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)&_pragma=synchronous(NORMAL)"

// ErrNotFound возвращается, когда пользователя с таким id нет.
var ErrNotFound = errors.New("user not found")

type User struct {
	ID   int64  `json:"id"`
	Name string `json:"name"`
}

type Store struct {
	db *sql.DB
}

// OpenStore открывает (или создаёт) файл БД и таблицу users.
func OpenStore(path string) (*Store, error) {
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

func (s *Store) AddUser(ctx context.Context, name string) (User, error) {
	res, err := s.db.ExecContext(ctx, "INSERT INTO users (name) VALUES (?)", name)
	if err != nil {
		return User{}, fmt.Errorf("insert user: %w", err)
	}
	id, err := res.LastInsertId()
	if err != nil {
		return User{}, fmt.Errorf("insert user: %w", err)
	}
	return User{ID: id, Name: name}, nil
}

func (s *Store) GetUser(ctx context.Context, id int64) (User, error) {
	var u User
	err := s.db.QueryRowContext(ctx, "SELECT id, name FROM users WHERE id = ?", id).
		Scan(&u.ID, &u.Name)
	if errors.Is(err, sql.ErrNoRows) {
		return User{}, ErrNotFound
	}
	if err != nil {
		return User{}, fmt.Errorf("select user %d: %w", id, err)
	}
	return u, nil
}
