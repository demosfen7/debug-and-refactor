// Команда go-server — HTTP API пользователей, порт api.py на Go.
package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	addr := flag.String("addr", envOr("API_ADDR", "127.0.0.1:5000"), "адрес, на котором слушает сервер")
	dbPath := flag.String("db", envOr("API_DB", "test.db"), "путь к файлу SQLite")
	flag.Parse()

	store, err := OpenStore(*dbPath)
	if err != nil {
		log.Fatal(err)
	}
	defer store.Close()

	srv := &http.Server{
		Addr:              *addr,
		Handler:           NewServer(store),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	errCh := make(chan error, 1)
	go func() {
		log.Printf("listening on http://%s (db: %s)", *addr, *dbPath)
		errCh <- srv.ListenAndServe()
	}()

	select {
	case err := <-errCh:
		// До Shutdown ListenAndServe возвращается только с настоящей ошибкой
		// (например, порт занят).
		store.Close()
		log.Fatalf("listen: %v", err)
	case <-ctx.Done():
	}

	// Ctrl+C / SIGTERM: даём текущим запросам завершиться, потом закрываем БД.
	log.Print("shutting down")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("shutdown: %v", err)
	}
}

func envOr(key, fallback string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return fallback
}
