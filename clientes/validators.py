import re

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


_RUT_PATTERN = re.compile(r"^(?P<body>\d{1,8})-?(?P<check_digit>[0-9K])$")


def normalize_rut(value):
    """Return a Chilean RUT in canonical form: digits-check digit."""
    if value is None:
        raise ValidationError("Ingresa un RUT.", code="required")

    compact = re.sub(r"[.\s]", "", str(value)).upper()
    match = _RUT_PATTERN.fullmatch(compact)
    if not match:
        raise ValidationError("Ingresa un RUT chileno válido.", code="invalid_rut")

    body = match.group("body")
    supplied_check_digit = match.group("check_digit")
    weight = 2
    total = 0

    for digit in reversed(body):
        total += int(digit) * weight
        weight = 2 if weight == 7 else weight + 1

    remainder = 11 - (total % 11)
    expected_check_digit = {
        11: "0",
        10: "K",
    }.get(remainder, str(remainder))

    if supplied_check_digit != expected_check_digit:
        raise ValidationError("El dígito verificador del RUT no es válido.", code="invalid_check_digit")

    return f"{int(body)}-{expected_check_digit}"


@deconstructible
class RutChilenoValidator:
    message = "Ingresa un RUT chileno válido."
    code = "invalid_rut"

    def __call__(self, value):
        try:
            normalize_rut(value)
        except ValidationError as exc:
            raise ValidationError(self.message, code=self.code) from exc

    def __eq__(self, other):
        return isinstance(other, self.__class__)
