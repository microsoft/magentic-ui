import { Modal, Input, message } from "antd";
import { useTranslation } from "react-i18next";
import { setLocalStorage } from "./utils";
import { appContext } from "../hooks/provider";
import * as React from "react";
import { Button } from "./common/Button";

type SignInModalProps = {
  isVisible: boolean;
  onClose: () => void;
};

const SignInModal = ({ isVisible, onClose }: SignInModalProps) => {
  const { t } = useTranslation();
  const { user, setUser } = React.useContext(appContext);
  const [email, setEmail] = React.useState(user?.email || "default");

  const isAlreadySignedIn = !!user?.email;

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(e.target.value);
  };

  const handleSignIn = () => {
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      message.error(t("signIn.usernameCannotBeEmpty"));
      return;
    }
    setUser({ ...user, email: trimmedEmail, name: trimmedEmail });
    setLocalStorage("user_email", trimmedEmail);
    onClose();
  };

  return (
    <Modal
      open={isVisible}
      footer={null}
      closable={isAlreadySignedIn}
      maskClosable={isAlreadySignedIn}
      onCancel={isAlreadySignedIn ? onClose : undefined}
    >
      <span className="text-lg">
        {t("signIn.enterUsername")}<br></br> {t("signIn.changeUsernameWillCreateNewProfile")}
      </span>
      <div className="mb-4">
        <Input
          type="text"
          placeholder={t("signIn.enterUsername")}
          value={email}
          onChange={handleEmailChange}
          className="shadow-sm"
        />
      </div>
      <div className="flex justify-center">
        <Button
          variant="primary"
          onClick={handleSignIn}
        >
          {t("signIn.signIn")}
        </Button>
      </div>
    </Modal>
  );
};

export default SignInModal;
