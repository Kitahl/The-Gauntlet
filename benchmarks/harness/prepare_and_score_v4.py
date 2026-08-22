import prepare_and_score_v2 as v2
import prepare_and_score_v3 as v3

# Exact public ARC-AGI source used for this run.
v2.ARC = "https://github.com/fchollet/ARC-AGI/archive/399030444e0ab0cc8b4e199870fb20b863846f34.zip"

if __name__ == "__main__":
    v3.main()
