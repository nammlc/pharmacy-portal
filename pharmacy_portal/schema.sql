-- ============================================================
-- Schema database cho Cổng tra cứu thông tin dược
-- Chạy: mysql -u root -p < schema.sql
-- (Hoặc dùng flask shell + db.create_all(), xem README.md)
-- ============================================================

CREATE DATABASE IF NOT EXISTS pharmacy_portal
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE pharmacy_portal;

CREATE TABLE nguoi_dung (
  id INT AUTO_INCREMENT PRIMARY KEY,
  ten_dang_nhap VARCHAR(100) NOT NULL UNIQUE,
  mat_khau_hash VARCHAR(255) NOT NULL,
  ho_ten VARCHAR(150),
  vai_tro VARCHAR(50) DEFAULT 'duoc_si',
  dang_hoat_dong BOOLEAN DEFAULT TRUE,
  ngay_tao DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_ten_dang_nhap (ten_dang_nhap)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
-- Lưu ý: mat_khau_hash phải được tạo bằng werkzeug.security.generate_password_hash
-- (chạy create_admin.py thay vì insert trực tiếp bằng SQL) để đảm bảo đúng định dạng hash.

CREATE TABLE thuoc (
  id INT AUTO_INCREMENT PRIMARY KEY,
  ten_thuoc VARCHAR(255) NOT NULL,
  hoat_chat VARCHAR(255),
  ham_luong VARCHAR(100),
  dang_bao_che VARCHAR(100),
  nhom_thuoc VARCHAR(150),
  nha_san_xuat VARCHAR(255),
  so_dang_ky VARCHAR(100),
  ngay_cap_nhat DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_ten_thuoc (ten_thuoc),
  INDEX idx_hoat_chat (hoat_chat)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE thuoc_tiem_truyen (
  id INT AUTO_INCREMENT PRIMARY KEY,
  thuoc_id INT NOT NULL,
  dung_moi_pha_loang VARCHAR(255),
  nong_do_toi_da VARCHAR(100),
  toc_do_truyen VARCHAR(255),
  thoi_gian_truyen VARCHAR(100),
  do_on_dinh VARCHAR(255),
  dieu_kien_bao_quan VARCHAR(255),
  canh_bao TEXT,
  nguon_tham_khao VARCHAR(255),
  FOREIGN KEY (thuoc_id) REFERENCES thuoc(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE tuong_hop_tuong_ky (
  id INT AUTO_INCREMENT PRIMARY KEY,
  thuoc_a_id INT NOT NULL,
  thuoc_b_id INT NOT NULL,
  trang_thai ENUM('tuong_hop','tuong_ky','chua_xac_dinh') NOT NULL DEFAULT 'chua_xac_dinh',
  mo_ta TEXT,
  nguon_tham_khao VARCHAR(255),
  FOREIGN KEY (thuoc_a_id) REFERENCES thuoc(id) ON DELETE CASCADE,
  FOREIGN KEY (thuoc_b_id) REFERENCES thuoc(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE tuong_tac_thuoc (
  id INT AUTO_INCREMENT PRIMARY KEY,
  thuoc_a_id INT NOT NULL,
  thuoc_b_id INT NOT NULL,
  muc_do ENUM('nhe','trung_binh','nang','chong_chi_dinh') NOT NULL DEFAULT 'trung_binh',
  co_che TEXT,
  hau_qua_lam_sang TEXT,
  xu_tri TEXT,
  nguon_tham_khao VARCHAR(255),
  FOREIGN KEY (thuoc_a_id) REFERENCES thuoc(id) ON DELETE CASCADE,
  FOREIGN KEY (thuoc_b_id) REFERENCES thuoc(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE thong_tin_thuoc (
  id INT AUTO_INCREMENT PRIMARY KEY,
  thuoc_id INT NOT NULL UNIQUE,
  chi_dinh TEXT,
  chong_chi_dinh TEXT,
  lieu_dung_nguoi_lon TEXT,
  lieu_dung_tre_em TEXT,
  tac_dung_phu TEXT,
  than_trong TEXT,
  phu_nu_co_thai_cho_con_bu TEXT,
  nguon_tham_khao VARCHAR(255),
  FOREIGN KEY (thuoc_id) REFERENCES thuoc(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE thong_tin_benh_nhan (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tieu_de VARCHAR(255) NOT NULL,
  danh_muc VARCHAR(150),
  noi_dung TEXT NOT NULL,
  ngay_dang DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
