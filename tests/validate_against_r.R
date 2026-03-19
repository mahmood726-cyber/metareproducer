# tests/validate_against_r.R
# Compare MetaReproducer DL/REML against metafor::rma()
library(metafor)

cat("=== MetaReproducer R Validation ===\n\n")

yi <- c(log(0.75), log(0.80), log(0.90), log(0.70), log(0.85))
sei <- c(0.20, 0.25, 0.30, 0.15, 0.22)

dl <- rma(yi, sei^2, method="DL")
reml <- rma(yi, sei^2, method="REML")

cat("Test 1: 5 binary studies\n")
cat(sprintf("  DL pooled:  %.8f  tau2: %.8f  I2: %.2f\n", dl$beta, dl$tau2, dl$I2))
cat(sprintf("  REML pooled: %.8f  tau2: %.8f  I2: %.2f\n", reml$beta, reml$tau2, reml$I2))

yi2 <- rep(log(0.80), 3)
sei2 <- rep(0.20, 3)
dl2 <- rma(yi2, sei2^2, method="DL")
cat(sprintf("\nTest 2: Homogeneous (DL tau2=%.10f)\n", dl2$tau2))

yi3 <- c(log(0.5), log(1.5))
sei3 <- c(0.2, 0.2)
dl3 <- rma(yi3, sei3^2, method="DL")
cat(sprintf("\nTest 3: k=2 (DL pooled=%.8f tau2=%.8f)\n", dl3$beta, dl3$tau2))

cat("\n--- JSON ---\n")
cat(sprintf('{"test1_dl_pooled": %.10f, "test1_dl_tau2": %.10f, "test1_dl_i2": %.4f,\n', dl$beta, dl$tau2, dl$I2))
cat(sprintf(' "test1_reml_pooled": %.10f, "test1_reml_tau2": %.10f,\n', reml$beta, reml$tau2))
cat(sprintf(' "test2_dl_tau2": %.10f, "test3_dl_pooled": %.10f, "test3_dl_tau2": %.10f}\n', dl2$tau2, dl3$beta, dl3$tau2))
