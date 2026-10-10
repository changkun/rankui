package utils

import (
	"fmt"
	"regexp"
	"strings"
	"unicode/utf8"

	"github.com/gohugoio/hugo/tpl"
	"github.com/spf13/cast"
)

func CountWords(s string) (int, error) {
	ss, err := cast.ToStringE(any(s))
	if err != nil {
		return 0, fmt.Errorf("failed to convert content to string: %w", err)
	}

	isCJKLanguage, err := regexp.MatchString(`\p{Han}|\p{Hangul}|\p{Hiragana}|\p{Katakana}`, ss)
	if err != nil {
		return 0, fmt.Errorf("failed to match regex pattern against string: %w", err)
	}

	if !isCJKLanguage {
		return len(strings.Fields(tpl.StripHTML(ss))), nil
	}

	counter := 0
	for _, word := range strings.Fields(tpl.StripHTML(ss)) {
		runeCount := utf8.RuneCountInString(word)
		if len(word) == runeCount {
			counter++
		} else {
			counter += runeCount
		}
	}

	return counter, nil
}
