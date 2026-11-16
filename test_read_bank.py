from read_bank import parse_amount

assert parse_amount("-1.280,00") == -1280

print("OK - parse_amount test passed")