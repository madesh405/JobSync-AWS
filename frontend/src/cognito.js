const REGION="us-east-1";

const CLIENT_ID="4bj4oa15u1ohudact7rlfvkb2j";

const COGNITO_ENDPOINT=
  `https://cognito-idp.${REGION}.amazonaws.com/`;

const STORAGE_KEY="jobsync_auth";

async function cognitoRequest(
  target,
  body
) {
  const response=await fetch(
    COGNITO_ENDPOINT,
    {
      method:"POST",
      headers:{
        "Content-Type":"application/x-amz-json-1.1",
        "X-Amz-Target":target
      },
      body:JSON.stringify(body)
    }
  );

  const data=await response.json();

  if (!response.ok) {
    throw new Error(
      data.message ||
      "Cognito authentication failed."
    );
  }

  return data;
}


export async function loginUser(
  email,
  password
) {
  const data=await cognitoRequest(
    "AWSCognitoIdentityProviderService.InitiateAuth",
    {
      AuthFlow:"USER_PASSWORD_AUTH",
      ClientId:CLIENT_ID,
      AuthParameters:{
        USERNAME:email,
        PASSWORD:password
      }
    }
  );

  const result=data.AuthenticationResult;

  if (!result) {
    throw new Error(
      "Cognito returned an unexpected authentication response."
    );
  }

  const auth={
    email,
    accessToken:result.AccessToken,
    idToken:result.IdToken,
    refreshToken:result.RefreshToken,
    expiresIn:result.ExpiresIn,
    authenticatedAt:Date.now()
  };

  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(auth)
  );

  return auth;
}


export function logoutUser() {
  localStorage.removeItem(
    STORAGE_KEY
  );
}


export function getCurrentUser() {
  const raw=
    localStorage.getItem(
      STORAGE_KEY
    );

  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    localStorage.removeItem(
      STORAGE_KEY
    );

    return null;
  }
}


export function getCurrentSession() {
  const user=getCurrentUser();

  if (!user) {
    return null;
  }

  const expiresAt=
    user.authenticatedAt +
    Number(user.expiresIn || 3600) *
      1000;

  if (Date.now() >= expiresAt) {
    logoutUser();
    return null;
  }

  return user;
}